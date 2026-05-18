fn main() {
    let mut a = 0;
    let mut b = 1;
    for _ in 0..10 {
        println!("{}", a);
        let next = a + b;
        a = b;
        b = next;
    }
}