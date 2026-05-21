using System;

namespace Fibonacci
{
    class Program
    {
        static void Main(string[] args)
        {
            Console.WriteLine("Fibonacci sequence up to 15 terms:");
            int n = 15;
            int a = 0, b = 1;

            Console.Write(a + " ");
            Console.Write(b + " ");

            for (int i = 3; i <= n; i++)
            {
                int c = a + b;
                Console.Write(c + " ");
                a = b;
                b = c;
            }

            Console.WriteLine(); // To move to a new line after the sequence
        }
    }
}