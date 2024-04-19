use std::fmt::{Debug, Formatter};
use std::path::Path;
use std::rc::Rc;
use std::sync::Mutex;

use signature::Signer;

use crate::API_VERSION;

#[derive(Clone, Debug, Default)]
pub struct Config {
    pub base_url: String,
    pub api_version: String,
    pub ssh_signer: Option<SshSigner>,
    pub auth_token: Option<String>,
}

#[derive(Clone)]
pub enum SshSigner {
    Agent(
        Box<ssh_key::PublicKey>,
        Box<Rc<Mutex<ssh_agent_client_rs::Client>>>,
    ),
    Key(Box<ssh_key::PrivateKey>),
}

impl Config {
    pub fn build_from_environment() -> anyhow::Result<Self> {
        let config = Self {
            base_url: std::env::var("SERVERADMIN_BASE_URL")?
                .trim_end_matches('/')
                .trim_end_matches("/api")
                .to_string(),
            api_version: API_VERSION.to_string(),
            ssh_signer: Self::get_signing_key()?,
            auth_token: std::env::var("SERVERADMIN_TOKEN").ok(),
        };

        Ok(config)
    }

    fn get_signing_key() -> anyhow::Result<Option<SshSigner>> {
        if let Ok(path) = std::env::var("SERVERADMIN_KEY_PATH") {
            let key = ssh_key::PrivateKey::read_openssh_file(Path::new(&path))?;

            return Ok(Some(SshSigner::Key(Box::new(key))));
        }

        let path = std::env::var("SSH_AUTH_SOCK").unwrap_or_default();
        let client = ssh_agent_client_rs::Client::connect(Path::new(&path))
            .map_err(|error| log::error!("Unable to connect to SSH agent: {error}"))
            .ok();

        if let Some(mut client) = client {
            let identities = client.list_identities()?;
            for key in identities {
                log::debug!(
                    "Test signing with SSH key {}",
                    key.fingerprint(ssh_key::HashAlg::Sha256)
                );

                if client.sign(&key, b"mest message").is_ok() {
                    log::debug!(
                        "Found compatible key: {}",
                        key.fingerprint(ssh_key::HashAlg::Sha256)
                    );

                    return Ok(Some(SshSigner::Agent(
                        Box::new(key),
                        Box::new(Rc::new(Mutex::new(client))),
                    )));
                }
            }
        }

        Ok(None)
    }
}

impl Debug for SshSigner {
    fn fmt(&self, f: &mut Formatter<'_>) -> std::fmt::Result {
        match self {
            SshSigner::Key(_key) => f.write_fmt(format_args!("Key: {}", self.get_public_key())),
            SshSigner::Agent(_key, _) => {
                f.write_fmt(format_args!("Agent: {}", self.get_public_key()))
            }
        }
    }
}

impl SshSigner {
    pub fn get_public_key(&self) -> String {
        let public_key = match self {
            SshSigner::Key(key) => key.public_key(),
            SshSigner::Agent(key, _) => key,
        };

        let key = public_key.to_openssh().unwrap();
        let mut key = key.split(' ');
        key.next();

        key.next().map(ToString::to_string).unwrap_or_default()
    }
}

impl Signer<ssh_key::Signature> for SshSigner {
    fn try_sign(&self, msg: &[u8]) -> Result<ssh_key::Signature, signature::Error> {
        match self {
            SshSigner::Key(key) => key.try_sign(msg),
            SshSigner::Agent(key, agent) => agent
                .lock()
                .unwrap()
                .sign(key, msg)
                .map_err(signature::Error::from_source),
        }
    }
}
