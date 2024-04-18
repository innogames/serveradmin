use std::fmt::Display;

use crate::config::Config;
use crate::query::Query;

pub type ServerObject = serde_json::Value;

pub const QUERY_ENDPOINT: &str = "dataset/query";

#[derive(Clone, Debug, serde::Deserialize, serde::Serialize)]
pub struct QueryResponse<T = ServerObject> {
    status: String,
    result: Vec<Server<T>>,
}

#[derive(Clone, Debug, serde::Deserialize, serde::Serialize)]
pub struct Server<T=ServerObject> {
    object_id: u64,
    #[serde(flatten)]
    attributes: T
}

pub async fn query_objects<T: serde::de::DeserializeOwned>(query: &Query) -> anyhow::Result<QueryResponse<T>> {
    let config = Config::build_from_environment()?;
    let response = request_api(QUERY_ENDPOINT, serde_json::to_value(query)?, config).await?;
    let response = response.error_for_status()?;

    Ok(response.json().await?)
}

pub async fn request_api(endpoint: impl Display, data: serde_json::Value, config: Config) -> anyhow::Result<reqwest::Response> {
    let client = reqwest::Client::new();
    let token = config.auth_token.unwrap_or_default();
    let body = serde_json::to_string(&data)?;
    let now = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH)?.as_secs();
    let url = format!("{}/{endpoint}", config.base_url);
    let request = client.post(url)
        .header("Content-Type", "application/json")
        .header("X-Timestamp", now.to_string())
        .header("X-API-Version", config.api_version)
        .header("X-SecurityToken", calculate_security_token(&token, now, &body))
        .header("X-Application", calculate_app_id(&token))
        .body(body.into_bytes());

    Ok(request.send().await?)
}

impl<T: serde::de::DeserializeOwned> IntoIterator for QueryResponse<T> {
    type Item = Server<T>;
    type IntoIter = std::vec::IntoIter<Server<T>>;

    fn into_iter(self) -> Self::IntoIter {
        self.result.into_iter()
    }
}

fn calculate_security_token(token: &String, now: u64, body: &str) -> String {
    use hmac::Mac;

    type HmacSha1 = hmac::Hmac<sha1::Sha1>;
    let mut hmac = HmacSha1::new_from_slice(token.as_bytes()).expect("Hmac can accept any size of key");
    hmac.update(format!("{now}:{body}").as_bytes());
    let result = hmac.finalize();

    result.into_bytes().iter().map(|byte| format!("{:02x}", byte)).collect::<String>()
}

fn calculate_app_id(token: &String) -> String {
    use sha1::Digest;
    let mut hasher = sha1::Sha1::new();
    hasher.update(token.as_bytes());
    let result = hasher.finalize();

    result.iter().map(|byte| format!("{:02x}", byte)).collect::<String>()
}
