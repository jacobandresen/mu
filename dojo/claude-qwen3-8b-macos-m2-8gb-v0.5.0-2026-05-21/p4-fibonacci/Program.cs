using System;

namespace Fibonacci
{
    class Program
    {
        static void Main(string[] args)
        {
            int n = 10;
            int prev1 = 0;
            int prev2 = 1;
            
            Console.WriteLine(prev1);
            Console.WriteLine(prev2);
            
            for (int i = 2; i < n; i++)
            {
                int next = prev1 + prev2;
                Console.WriteLine(next);
                prev1 = prev2;
                prev2 = next;
            }
        }
    }
}