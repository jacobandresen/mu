using System;

public class Fibonacci {
    public static void Main(string[] args) {
        int n = 10; // Change this value to generate more or fewer Fibonacci numbers
        for (int i = 0; i < n; i++) {
            Console.WriteLine(Fib(i));
        }
    }

    private static long Fib(int n) {
        if (n <= 1) return n;
        else return Fib(n - 1) + Fib(n - 2);
    }
}