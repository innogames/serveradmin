use adminapi::filter::{empty, not, regexp};
use adminapi::new_object::NewObject;
use adminapi::query::Query;

#[tokio::main]
pub async fn main() -> anyhow::Result<()> {
    env_logger::init();
    let mut server = Query::builder()
        .filter("hostname", regexp(".*payment-staging.*"))
        .filter("os", not(empty()))
        .restrict(["hostname", "responsible_admin", "os"])
        .build()
        .request()
        .await?
        .all()
        .pop()
        .ok_or(anyhow::anyhow!("No servers returned"))?;

    server
        .set("os", "bookworm")?
        .add("responsible_admin", "yannik.schwiegerr")?
        .remove("responsible_admin", "yannik.schwieger")?;

    server.commit().await?;

    let mut new_sg = NewObject::request_new("service_group").await?;
    new_sg
        .set("hostname", "yannik-adminapi-rs-2.test.sg")
        .set("project", "test")
        .add("responsible_admin", "yannik.schwieger")
        .add("protocol_ports_inbound", "tcp443");
    let mut created_sg = new_sg.commit().await?;
    created_sg
        .add("protocol_ports_inbound", "tcp80")?
        .add("sg_allow_from", "yannik-adminapi-rs-2.test.sg")?
        .add("sg_allow_to", "yannik-adminapi-rs-2.test.sg")?
        .commit()
        .await?;

    Ok(())
}
