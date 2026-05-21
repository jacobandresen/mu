using System;

public class Fibonacci
{
    public static void Main(string[] args)
    {
        Console.WriteLine("Fibonacci Sequence:");
        long n = 1;
        long next = 1;

        for (int i = 0; i < 10; i++)
        {
            Console.Write(n + ", ");
            long temp = n + next;
            n = next;
            next = temp;
        }
        Console.WriteLine("\n");
    }
}