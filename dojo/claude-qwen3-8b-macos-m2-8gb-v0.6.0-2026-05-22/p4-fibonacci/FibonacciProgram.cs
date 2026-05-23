using System;

class Program
{
    static void Main()
    {
        int n = 10;
        int[] fib = new int[n];
        fib[0] = 0;
        fib[1] = 1;
        
        for (int i = 2; i < n; i++)
        {
            fib[i] = fib[i - 1] + fib[i - 2];
        }
        
        Console.WriteLine("Fibonacci sequence up to " + n + ":");
        for (int i = 0; i < n; i++)
        {
            Console.Write(fib[i] + " ");
        }
    }
}