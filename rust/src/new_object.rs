use std::ops::{Deref, DerefMut};

use crate::api::{commit_changes, new_object, NewObjectResponse, Server};
use crate::commit::{AttributeValue, Commit, Dataset};
use crate::query::Query;

pub struct NewObject {
    attributes: Dataset,
}

impl NewObject {
    pub async fn request_new(servertype: impl ToString) -> anyhow::Result<Self> {
        let servertype = servertype.to_string();
        let NewObjectResponse { result } = new_object(&servertype).await?;

        Ok(Self {
            attributes: result,
        })
    }

    pub async fn commit(self) -> anyhow::Result<Server> {
        let AttributeValue::String(hostname) = self.attributes.get("hostname") else {
            return Err(anyhow::anyhow!("Required attribute 'hostname' is missing"));
        };
        let commit = Commit::new().create(self.attributes);
        commit_changes(&commit).await?;

        Query::builder()
            .filter("hostname", hostname)
            .build()
            .request()
            .await?
            .one()
    }
}

impl Deref for NewObject {
    type Target = Dataset;

    fn deref(&self) -> &Self::Target {
        &self.attributes
    }
}

impl DerefMut for NewObject {
    fn deref_mut(&mut self) -> &mut Self::Target {
        &mut self.attributes
    }
}
