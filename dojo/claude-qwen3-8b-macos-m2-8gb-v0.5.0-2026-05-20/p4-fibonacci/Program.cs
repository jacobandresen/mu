using System;

namespace Fibonacci
{
    class Program
    {
        static void Main(string[] args)
        {
            int n = 10; // Number of terms
            int firstTerm = 0, secondTerm = 1;

            Console.WriteLine("Fibonacci Sequence:");
            for (int i = 1; i <= n; i++)
            {
                Console.Write(firstTerm + " ");
                int nextTerm = firstTerm + secondTerm;
                firstTerm = secondTerm;
                secondTerm = nextTerm;
            }
        }
    }
}