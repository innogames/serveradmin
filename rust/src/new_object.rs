use std::ops::{Deref, DerefMut};

use crate::api::{commit_changes, new_object, NewObjectResponse, Server};
use crate::commit::{AttributeValue, Changeset, Commit, Dataset};
use crate::query::Query;

#[derive(Clone, Debug)]
pub struct NewObject {
    object_id: Option<u64>,
    server: Server,
    deferred_changes: Changeset,
}

impl NewObject {
    pub fn from_dataset(dataset: Dataset) -> Self {
        Self {
            object_id: None,
            server: Server {
                object_id: 0,
                attributes: dataset,
                changes: Default::default(),
            },
            deferred_changes: Default::default(),
        }
    }

    pub async fn request_new(servertype: impl ToString) -> anyhow::Result<Self> {
        let servertype = servertype.to_string();
        let NewObjectResponse { result } = new_object(&servertype).await?;

        Ok(Self {
            object_id: None,
            server: Server {
                object_id: 0,
                attributes: result,
                changes: Default::default(),
            },
            deferred_changes: Default::default(),
        })
    }

    pub async fn get_or_create(
        servertype: impl ToString,
        hostname: impl ToString,
    ) -> anyhow::Result<Self> {
        let mut new_object = Self::request_new(servertype.to_string()).await?;

        if let Ok(server) = Query::builder()
            .filter("hostname", hostname.to_string())
            .restrict(new_object.server.attributes.keys())
            .build()
            .request()
            .await?
            .one()
        {
            new_object.object_id = Some(server.object_id);
            new_object.server = server;
        }

        Ok(new_object)
    }

    pub fn is_new(&self) -> bool {
        self.object_id.is_none()
    }

    pub fn has_changes(&self) -> bool {
        if self.is_new() {
            return true;
        }

        self.server.has_changes() || self.deferred_changes.has_changes()
    }

    ///
    /// Commits the new object
    ///
    /// The changes done in [NewObject::deferred] will not be submitted yet, but the returned [Server]
    /// object is preloaded with them.
    ///
    pub async fn commit(mut self) -> anyhow::Result<Server> {
        let AttributeValue::String(hostname) = self.server.get("hostname") else {
            return Err(anyhow::anyhow!("Required attribute 'hostname' is missing"));
        };

        if self.is_new() {
            commit_changes(&Commit::new().create(self.server.attributes)).await?;
        } else {
            self.server.commit().await?;
        }

        let mut server = Query::builder()
            .filter("hostname", hostname)
            .build()
            .request()
            .await?
            .one()?;

        server.changes = self.deferred_changes;

        Ok(server)
    }

    ///
    /// Gets the initial commit data and the follow-up commit of deferred changes
    ///
    pub fn get_commit(self) -> (Commit, Commit) {
        (
            Commit::new().create(self.server.attributes),
            Commit::new().update(self.deferred_changes),
        )
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
            attributes: self.server.attributes.clone(),
            changes: std::mem::take(&mut self.deferred_changes),
        };

        let output = callback(&mut server);

        self.deferred_changes = std::mem::take(&mut server.changes);

        output
    }
}

impl Deref for NewObject {
    type Target = Server;

    fn deref(&self) -> &Self::Target {
        &self.server
    }
}

impl DerefMut for NewObject {
    fn deref_mut(&mut self) -> &mut Self::Target {
        &mut self.server
    }
}
