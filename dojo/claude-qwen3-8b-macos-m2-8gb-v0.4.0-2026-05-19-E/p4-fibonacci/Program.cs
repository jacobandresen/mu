using System;

namespace Fibonacci
{
    class Program
    {
        static void Main(string[] args)
        {
            int n = 10;
            int a = 0, b = 1;

            Console.WriteLine("Fibonacci sequence up to " + n + " terms:");
            for (int i = 1; i <= n; i++)
            {
                Console.Write(a + " ");
                int temp = a + b;
                a = b;
                b = temp;
            }
        }
    }
}