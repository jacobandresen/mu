using System;

namespace Fibonacci
{
    class Program
    {
        static void Main(string[] args)
        {
            int n = 10; // Number of terms to generate
            int a = 0, b = 1, c;
            Console.WriteLine("Fibonacci Series:");
            for (int i = 0; i < n; i++)
            {
                Console.Write(a + " ");
                c = a + b;
                a = b;
                b = c;
            }
        }
    }
}