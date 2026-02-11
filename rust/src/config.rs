use std::fmt::Debug;

use crate::ssh::SshSigner;
use crate::API_VERSION;

pub const ENV_NAME_BASE_URL: &str = "SERVERADMIN_BASE_URL";
pub const ENV_NAME_TOKEN: &str = "SERVERADMIN_TOKEN";

#[derive(Clone, Debug, Default)]
pub struct Config {
    pub base_url: String,
    pub api_version: String,
    pub ssh_signer: Option<SshSigner>,
    pub auth_token: Option<String>,
}

impl Config {
    pub fn build_from_environment() -> crate::Result<Self> {
        let config = Self {
            base_url: std::env::var(ENV_NAME_BASE_URL)?
                .trim_end_matches('/')
                .trim_end_matches("/api")
                .to_string(),
            api_version: API_VERSION.to_string(),
            ssh_signer: SshSigner::try_from_environment()?,
            auth_token: std::env::var(ENV_NAME_TOKEN).ok(),
        };

        Ok(config)
    }
}
