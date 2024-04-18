use std::fmt::Display;

use crate::commit::{AttributeChange, Changeset, Commit, Dataset, IntoAttributeValue};
use crate::config::Config;
use crate::query::Query;

pub const QUERY_ENDPOINT: &str = "dataset/query";
pub const COMMIT_ENDPOINT: &str = "dataset/commit";
pub const NEW_OBJECT_ENDPOINT: &str = "dataset/new_object";

#[derive(Clone, Debug, serde::Deserialize, serde::Serialize)]
pub struct QueryResponse<T = Dataset> {
    pub status: String,
    pub result: Vec<Server<T>>,
}

#[derive(Clone, Debug, serde::Deserialize, serde::Serialize)]
pub struct NewObjectResponse {
    pub result: Dataset,
}

#[derive(Clone, Debug, serde::Deserialize, serde::Serialize)]
pub struct CommitResponse {
    pub status: String,
}

pub async fn query_objects<T: serde::de::DeserializeOwned>(
    query: &Query,
) -> anyhow::Result<QueryResponse<T>> {
    let config = Config::build_from_environment()?;
    let response = request_api(QUERY_ENDPOINT, serde_json::to_value(query)?, config).await?;
    let response = response.error_for_status()?;

    Ok(response.json().await?)
}

pub async fn new_object(servertype: impl Display) -> anyhow::Result<NewObjectResponse> {
    let config = Config::build_from_environment()?;
    let response = request_api(
        format!("{NEW_OBJECT_ENDPOINT}?servertype={servertype}"),
        serde_json::Value::Null,
        config,
    )
    .await?;
    let response = response.error_for_status()?;

    Ok(response.json().await?)
}

pub async fn commit_changes(commit: &Commit) -> anyhow::Result<CommitResponse> {
    let config = Config::build_from_environment()?;
    let response = request_api(COMMIT_ENDPOINT, serde_json::to_value(commit)?, config).await?;
    let response = response.error_for_status()?;

    Ok(response.json().await?)
}

pub async fn request_api(
    endpoint: impl Display,
    data: serde_json::Value,
    config: Config,
) -> anyhow::Result<reqwest::Response> {
    let client = reqwest::Client::new();
    let token = config.auth_token.unwrap_or_default();
    let body = serde_json::to_string(&data)?;
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)?
        .as_secs();
    let url = format!("{}/{endpoint}", config.base_url);
    let request = client
        .post(url)
        .header("Content-Type", "application/json")
        .header("X-Timestamp", now.to_string())
        .header("X-API-Version", config.api_version)
        .header(
            "X-SecurityToken",
            calculate_security_token(&token, now, &body),
        )
        .header("X-Application", calculate_app_id(&token))
        .body(body.into_bytes());

    Ok(request.send().await?)
}

#[derive(Clone, Debug, serde::Deserialize, serde::Serialize)]
pub struct Server<T = Dataset> {
    pub object_id: u64,
    #[serde(flatten)]
    pub attributes: T,
    #[serde(skip, default)]
    pub(crate) changes: Changeset,
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
    let mut hmac =
        HmacSha1::new_from_slice(token.as_bytes()).expect("Hmac can accept any size of key");
    hmac.update(format!("{now}:{body}").as_bytes());
    let result = hmac.finalize();

    result
        .into_bytes()
        .iter()
        .fold(String::new(), |hash, byte| format!("{hash}{byte:02x}"))
}

fn calculate_app_id(token: &String) -> String {
    use sha1::Digest;
    let mut hasher = sha1::Sha1::new();
    hasher.update(token.as_bytes());
    let result = hasher.finalize();

    result
        .iter()
        .fold(String::new(), |hash, byte| format!("{hash}{byte:02x}"))
}

impl Server {
    pub fn set(
        &mut self,
        attribute: impl ToString,
        value: impl IntoAttributeValue + 'static,
    ) -> anyhow::Result<&mut Self> {
        let new = value.into_attribute_value();
        let attribute = attribute.to_string();

        if self.attributes.get(&attribute).is_array() {
            return Err(anyhow::anyhow!(
                "Attribute is a multi attribute, set is not supported!"
            ));
        }

        let old = self.attributes.get(&attribute);
        self.attributes.set(attribute.clone(), new.clone());
        self.changes
            .attributes
            .insert(attribute, AttributeChange::Update { old, new });

        Ok(self)
    }

    pub fn add(
        &mut self,
        attribute: impl ToString,
        value: impl IntoAttributeValue + 'static,
    ) -> anyhow::Result<&mut Self> {
        let value = value.into_attribute_value();
        let attribute = attribute.to_string();

        if !self.attributes.get(&attribute).is_array() {
            return Err(anyhow::anyhow!(
                "add is only supported with multi attributes"
            ));
        }

        self.attributes.add(attribute.clone(), value.clone());
        let entry = self
            .changes
            .attributes
            .entry(attribute)
            .or_insert(AttributeChange::Multi {
                remove: vec![],
                add: vec![],
            });

        if let AttributeChange::Multi { add, .. } = entry {
            add.push(value);
        }
        Ok(self)
    }

    pub fn remove(
        &mut self,
        attribute: impl ToString,
        value: impl IntoAttributeValue + 'static,
    ) -> anyhow::Result<&mut Self> {
        let value = value.into_attribute_value();
        let attribute = attribute.to_string();

        if !self.attributes.get(&attribute).is_array() {
            return Err(anyhow::anyhow!(
                "remove is only supported with multi attributes"
            ));
        }

        self.attributes.remove(attribute.clone(), value.clone());
        let entry = self
            .changes
            .attributes
            .entry(attribute)
            .or_insert(AttributeChange::Multi {
                remove: vec![],
                add: vec![],
            });

        if let AttributeChange::Multi { remove, .. } = entry {
            remove.push(value);
        }

        Ok(self)
    }

    pub fn changeset(&self) -> Changeset {
        let mut set = self.changes.clone();
        set.object_id = self.object_id;

        set
    }
}

impl<T: serde::de::DeserializeOwned> QueryResponse<T> {
    pub fn one(mut self) -> anyhow::Result<Server<T>> {
        if self.result.len() > 1 {
            return Err(anyhow::anyhow!("Result has more then one item!"));
        }

        self.result
            .pop()
            .ok_or(anyhow::anyhow!("No result returned!"))
    }

    pub fn all(self) -> Vec<Server<T>> {
        self.result
    }
}
