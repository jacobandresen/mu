using System;

public class Program
{
    public static void Main(string[] args)
    {
        int n = 10; // Number of terms to generate
        Console.WriteLine($"Fibonacci sequence up to {n} terms:");

        long a = 0;
        long b = 1;

        if (n >= 1)
        {
            Console.Write(a + ", ");
        }
        if (n >= 2)
        {
            Console.Write(b + ", ");
        }

        for (int i = 3; i <= n; i++)
        {
            long next = a + b;
            Console.Write(next + ", ");
            a = b;
            b = next;
        }
        Console.WriteLine("\n");
    }
}