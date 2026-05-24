using System;
using Xunit;

public class FibonacciTests {
    [Fact]
    public void TestFibonacci() {
        Assert.Equal(0, Fibonacci.Calculate(0));
        Assert.Equal(1, Fibonacci.Calculate(1));
        Assert.Equal(1, Fibonacci.Calculate(2));
        Assert.Equal(2, Fibonacci.Calculate(3));
        Assert.Equal(3, Fibonacci.Calculate(4));
        Assert.Equal(5, Fibonacci.Calculate(5));
        Assert.Equal(8, Fibonacci.Calculate(6));
        Assert.Equal(13, Fibonacci.Calculate(7));
        Assert.Equal(21, Fibonacci.Calculate(8));
        Assert.Equal(34, Fibonacci.Calculate(9));
    }
}