fn main() {
    let mut a = 0;
    let mut b = 1;
    let mut count = 0;
    let mut n = 10;

    while count < n {
        println!("{}", a);
        let temp = a;
        a = b;
        b = temp + b;
        count += 1;
    }
}