using System;

namespace FibonacciApp
{
    class Program
    {
        static void Main(string[] args)
        {
            Console.Write("Enter the number of terms: ");
            string input = Console.ReadLine();
            int n;
            while (true)
            {
                if (int.TryParse(input, out n) && n > 0)
                {
                    break;
                }
                Console.WriteLine("Invalid input. Please enter a positive integer.");
                input = Console.ReadLine();
            }

            if (n == 1)
            {
                Console.WriteLine(0);
            }
            else
            {
                int a = 0, b = 1;
                Console.WriteLine(a);
                for (int i = 2; i <= n; i++)
                {
                    int next = a + b;
                    Console.WriteLine(next);
                    a = b;
                    b = next;
                }
            }
        }
    }
}