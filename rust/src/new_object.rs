use std::ops::{Deref, DerefMut};

use crate::api::{commit_changes, new_object, NewObjectResponse, Server};
use crate::commit::{AttributeValue, Changeset, Commit, Dataset};
use crate::query::Query;

#[derive(Clone, Debug)]
pub struct NewObject {
    object_id: Option<u64>,
    attributes: Dataset,
    changeset: Changeset,
}

impl NewObject {
    pub async fn request_new(servertype: impl ToString) -> anyhow::Result<Self> {
        let servertype = servertype.to_string();
        let NewObjectResponse { result } = new_object(&servertype).await?;

        Ok(Self {
            object_id: None,
            attributes: result,
            changeset: Default::default(),
        })
    }

    pub async fn get_or_create(
        servertype: impl ToString,
        hostname: impl ToString,
    ) -> anyhow::Result<Self> {
        let mut new_object = Self::request_new(servertype).await?;

        if let Ok(server) = Query::builder()
            .filter("hostname", hostname.to_string())
            .restrict(new_object.attributes.keys())
            .build()
            .request()
            .await?
            .one()
        {
            new_object.object_id = Some(server.object_id);
            new_object.attributes = server.attributes;
        }

        Ok(new_object)
    }

    ///
    /// Commits the new object
    ///
    /// The changes done in [NewObject::deferred] will not be submitted yet, but the returned [Server]
    /// object is preloaded with them.
    ///
    pub async fn commit(self) -> anyhow::Result<Server> {
        let AttributeValue::String(hostname) = self.attributes.get("hostname") else {
            return Err(anyhow::anyhow!("Required attribute 'hostname' is missing"));
        };
        let commit = Commit::new().create(self.attributes);
        commit_changes(&commit).await?;

        let mut server = Query::builder()
            .filter("hostname", hostname)
            .build()
            .request()
            .await?
            .one()?;

        server.changes = self.changeset;

        Ok(server)
    }

    ///
    /// The deferred method allows you to pre-update the newly created object
    ///
    /// It allows you to already prepare relations before other objects are created, making the new
    /// object creation with relations a very simple 2-stage process.
    ///
    /// The input [Server] object for the `callback` is loaded with the [Dataset] of the current
    /// object. Keep in mind though, that there are some attributes that are only filled after the
    /// object is created
    ///
    pub fn deferred<R>(&mut self, callback: impl FnOnce(&mut Server) -> R) -> R {
        let mut server = Server {
            object_id: 0,
            attributes: self.attributes.clone(),
            changes: std::mem::take(&mut self.changeset),
        };

        let output = callback(&mut server);

        self.changeset = std::mem::take(&mut server.changes);

        output
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
