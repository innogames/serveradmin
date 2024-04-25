use adminapi::cli::parse_filter_args;
use adminapi::query::Query;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    env_logger::init();

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
