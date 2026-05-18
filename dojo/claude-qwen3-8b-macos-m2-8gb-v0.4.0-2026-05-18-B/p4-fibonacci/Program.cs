using System;

namespace Fibonacci
{
    class Program
    {
        static void Main()
        {
            int n = 10; // Number of terms
            int a = 0, b = 1;

            Console.WriteLine("Fibonacci Sequence:");
            for (int i = 1; i <= n; i++)
            {
                Console.Write(a + " ");
                int temp = a;
                a = b;
                b = temp + b;
            }
        }
    }
}