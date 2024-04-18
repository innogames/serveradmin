use crate::API_VERSION;

#[derive(Clone, Debug, Default)]
pub struct Config {
    pub base_url: String,
    pub api_version: String,
    pub ssh_signer: Option<()>,
    pub auth_token: Option<String>,
}

impl Config {
    pub fn build_from_environment() -> anyhow::Result<Self> {
        Ok(Self {
            base_url: std::env::var("SERVERADMIN_BASE_URL")?,
            api_version: API_VERSION.to_string(),
            ssh_signer: None,
            auth_token: std::env::var("SERVERADMIN_TOKEN").ok(),
        })
    }
}
