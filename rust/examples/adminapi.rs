use adminapi::cli::parse_filter_args;
use adminapi::query::Query;
use tracing_subscriber::EnvFilter;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::from_default_env())
        .init();

    let mut args = std::env::args();
    args.next();

    let filters = parse_filter_args(args)?;

    let query = Query::builder()
        .filters(filters)
        .restrict(["hostname", "responsible_admin", "os"])
        .build();

    let servers = query.request().await?;
    for server in servers.into_iter() {
        println!("{server:#?}");
    }

    Ok(())
}
