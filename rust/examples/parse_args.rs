use adminapi::cli::parse_filter_args;

pub fn main() {
    let mut args = std::env::args();
    args.next();

    match parse_filter_args(args) {
        Ok(arg) => {
            println!("{arg:#?}");
        }
        Err(err) => {
            eprintln!("{err:#?}");
        }
    }
}
