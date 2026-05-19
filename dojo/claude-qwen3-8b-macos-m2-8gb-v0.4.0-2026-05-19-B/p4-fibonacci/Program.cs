using System;

namespace FibonacciApp
{
    class Program
    {
        static void Main(string[] args)
        {
            int count = 20;
            int a = 0, b = 1;
            Console.WriteLine("Fibonacci Sequence (first 20 terms):");
            for (int i = 0; i < count; i++)
            {
                Console.Write(a + " ");
                int temp = a;
                a = b;
                b = temp + b;
            }
        }
    }
}