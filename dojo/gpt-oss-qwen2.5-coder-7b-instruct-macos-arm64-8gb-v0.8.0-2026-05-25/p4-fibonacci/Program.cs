using System;

namespace FibonacciGenerator
{
    class Program
    {
        static void Main(string[] args)
        {
            int n = 10; // Number of terms to generate
            Console.WriteLine("Fibonacci Sequence:");
            for (int i = 0; i < n; i++)
            {
                Console.Write(Fibonacci(i) + " ");
            }
        }

        static int Fibonacci(int num)
        {
            if (num <= 1)
                return num;
            else
                return Fibonacci(num - 1) + Fibonacci(num - 2);
        }
    }
}