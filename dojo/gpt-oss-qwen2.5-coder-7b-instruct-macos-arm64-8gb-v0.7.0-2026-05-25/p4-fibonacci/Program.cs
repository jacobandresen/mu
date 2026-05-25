using System;

namespace FibonacciGenerator
{
    class Program
    {
        static void Main(string[] args)
        {
            int n = 10; // Change this value to generate more or fewer Fibonacci numbers
            Console.WriteLine("Fibonacci sequence up to {0}:", n);
            for (int i = 0; i < n; i++)
            {
                Console.Write(Fibonacci(i) + " ");
            }
        }

        static int Fibonacci(int number)
        {
            if (number <= 1)
                return number;
            else
                return Fibonacci(number - 1) + Fibonacci(number - 2);
        }
    }
}