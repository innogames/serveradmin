use std::collections::HashSet;

use crate::api::{query_objects, QueryResponse};
use crate::filter::{AttributeFilter, IntoFilterValue};

#[derive(Clone, Debug, Default, serde::Deserialize, serde::Serialize)]
pub struct Query {
    pub filters: AttributeFilter,
    pub restrict: HashSet<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub order_by: Option<String>,
}

#[derive(Clone, Debug, Default, serde::Deserialize, serde::Serialize)]
pub struct QueryBuilder(Query);

impl Query {
    pub fn new() -> Self {
        Default::default()
    }

    pub fn builder() -> QueryBuilder {
        Default::default()
    }

    pub async fn request(&self) -> anyhow::Result<QueryResponse> {
        query_objects(self).await
    }

    pub async fn request_typed<T: serde::de::DeserializeOwned>(&self) -> anyhow::Result<QueryResponse<T>> {
        query_objects::<T>(self).await
    }
}

impl QueryBuilder {
    pub fn new() -> Self {
        Default::default()
    }

    pub fn filter(mut self, attribute: impl ToString, value: impl IntoFilterValue + 'static) -> Self {
        self.0.filters.insert(attribute.to_string(), value.into_filter_value());

        self
    }

    pub fn restrict<S: ToString, I: IntoIterator<Item=S>>(mut self, attributes: I) -> Self {
        self.0.restrict = HashSet::from_iter(attributes.into_iter().map(|v| v.to_string()));

        self
    }

    pub fn order_by<S: ToString, T: Into<Option<S>>>(mut self, value: T) -> Self {
        self.0.order_by = value.into().as_ref().map(ToString::to_string);

        self
    }

    pub fn build(mut self) -> Query {
        if self.0.restrict.is_empty() {
            self.0.restrict.insert(String::from("hostname"));
        }

        self.0.restrict.insert(String::from("object_id"));

        self.0
    }
}
