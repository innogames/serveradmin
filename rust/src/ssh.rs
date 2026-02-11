use std::{
    fmt::{Debug, Formatter},
    path::Path,
    sync::{Arc, Mutex},
};

use signature::Signer;
use ssh_encoding::Encode;

pub const ENV_NAME_KEY_PATH: &str = "SERVERADMIN_KEY_PATH";
pub const ENV_NAME_SSH_AGENT: &str = "SSH_AUTH_SOCK";

#[derive(Clone)]
pub enum SshSigner {
    Agent(Identity, Arc<Mutex<WrappedSshClient>>),
    Key(ssh_key::PrivateKey),
}

#[derive(Debug, Clone)]
pub enum Identity {
    PublicKey(ssh_key::PublicKey),
    Certificate(ssh_key::Certificate),
}

impl Debug for SshSigner {
    fn fmt(&self, f: &mut Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Agent(arg0, _) => f.debug_tuple("Agent").field(arg0).finish(),
            Self::Key(arg0) => f.debug_tuple("Key").field(arg0).finish(),
        }
    }
}

impl SshSigner {
    /// Tries to find a ssh key or agent to sign messages
    ///
    /// It will make sure that whatever is found can actually be used for signing
    pub fn try_from_environment() -> crate::Result<Option<Self>> {
        if let Ok(path) = std::env::var(ENV_NAME_KEY_PATH) {
            let key = ssh_key::PrivateKey::read_openssh_file(Path::new(&path))?;

            return Ok(Some(SshSigner::Key(key)));
        }

        let path = std::env::var(ENV_NAME_SSH_AGENT).unwrap_or_default();
        let client = ssh_agent_client_rs::Client::connect(Path::new(&path))
            .map_err(|error| tracing::debug!("Unable to connect to SSH agent: {error}"))
            .ok();

        if let Some(mut client) = client {
            let identities = client.list_all_identities()?;

            for identity in identities {
                tracing::debug!(?identity, "Test signing with SSH key");

                let identity = match &identity {
                    ssh_agent_client_rs::Identity::PublicKey(cow) => {
                        Identity::PublicKey(cow.clone().into_owned())
                    }
                    ssh_agent_client_rs::Identity::Certificate(cow) => {
                        Identity::Certificate(cow.clone().into_owned())
                    }
                };

                if client.sign(&identity, b"mest message").is_ok() {
                    tracing::debug!(?identity, "Found compatible key");

                    return Ok(Some(SshSigner::Agent(
                        identity,
                        Arc::new(Mutex::new(WrappedSshClient { client })),
                    )));
                }
            }
        }

        Ok(None)
    }

    /// Signes the given message bytes
    pub fn sign_message<M: AsRef<[u8]>>(&self, message: M) -> crate::Result<String> {
        let signature = self.try_sign(message.as_ref())?;
        let len = Encode::encoded_len_prefixed(&signature)?;
        let base64_len = (((len.saturating_mul(4)) / 3).saturating_add(3)) & !3;
        let mut buf = vec![0; base64_len];
        let mut writer = ssh_encoding::Base64Writer::new(&mut buf)?;
        signature.encode(&mut writer)?;
        let signature = writer.finish()?;

        Ok(signature.to_string())
    }

    /// Get's an OpenSSH formatted public key blob (RFC 4253)
    pub fn get_public_key(&self) -> crate::Result<String> {
        let public_key = match self {
            SshSigner::Agent(identity, _) => identity.get_public_key()?,
            SshSigner::Key(private_key) => private_key.public_key().to_openssh()?,
        };

        let key_parts = public_key.split(" ");

        key_parts
            .skip(1) // Skipts the algorithm
            .next() // Takes only the key
            .map(ToString::to_string)
            .ok_or(crate::Error::PublicKeyFormatError(public_key))
    }
}

impl Signer<ssh_key::Signature> for SshSigner {
    fn try_sign(&self, msg: &[u8]) -> Result<ssh_key::Signature, signature::Error> {
        match self {
            SshSigner::Key(key) => key.try_sign(msg),
            SshSigner::Agent(identity, agent) => {
                let mut agent = agent.lock().unwrap();

                agent
                    .client
                    .sign(identity, msg)
                    .map_err(signature::Error::from_source)
            }
        }
    }
}

pub struct WrappedSshClient {
    client: ssh_agent_client_rs::Client,
}

unsafe impl Send for WrappedSshClient {}
unsafe impl Sync for WrappedSshClient {}

impl<'a> Into<ssh_agent_client_rs::Identity<'a>> for Identity {
    fn into(self) -> ssh_agent_client_rs::Identity<'a> {
        match self {
            Identity::PublicKey(value) => ssh_agent_client_rs::Identity::from(value),
            Identity::Certificate(value) => ssh_agent_client_rs::Identity::from(value),
        }
    }
}

impl<'a> Into<ssh_agent_client_rs::Identity<'a>> for &'a Identity {
    fn into(self) -> ssh_agent_client_rs::Identity<'a> {
        match self {
            Identity::PublicKey(value) => ssh_agent_client_rs::Identity::from(value),
            Identity::Certificate(value) => ssh_agent_client_rs::Identity::from(value),
        }
    }
}

impl Identity {
    /// Get's an OpenSSH formatted public key blob (RFC 4253) with the comment and key type
    pub fn get_public_key(&self) -> crate::Result<String> {
        match self {
            Identity::PublicKey(public_key) => Ok(public_key.to_openssh()?),
            Identity::Certificate(certificate) => {
                let key = ssh_key::PublicKey::from(certificate.public_key().clone());

                Ok(key.to_openssh()?)
            }
        }
    }
}
