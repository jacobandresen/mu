using System;

namespace Fibonacci
{
    class Program
    {
        static void Main(string[] args)
        {
            Console.WriteLine("Fibonacci Sequence:");
            int n = 10; // Number of terms to generate
            int first = 0, second = 1;

            for (int i = 0; i < n; i++)
            {
                Console.WriteLine(first);
                int next = first + second;
                first = second;
                second = next;
            }
        }
    }
}
