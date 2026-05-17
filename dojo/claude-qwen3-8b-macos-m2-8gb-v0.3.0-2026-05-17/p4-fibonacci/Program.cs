using System;

class Program
{
    static void Main(string[] args)
    {
        int n = 10;
        long[] fibSequence = new long[n];
        
        fibSequence[0] = 0;
        fibSequence[1] = 1;
        
        for (int i = 2; i < n; i++)
        {
            fibSequence[i] = fibSequence[i - 1] + fibSequence[i - 2];
        }
        
        Console.WriteLine("Fibonacci sequence of " + n + " numbers:");
        for (int i = 0; i < n; i++)
        {
            Console.WriteLine(fibSequence[i]);
        }
    }
}