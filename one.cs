using System;
namespace something
{
class Program
{
  static void one()
  {
    string a = Console.ReadLine();
  }
static void Main(string[] args)
{
Console.WriteLine("write any thing");
  string a = Console.ReadLine();
  one();
  if (a == "1")
  {
    one();
  }
  else
  {
    one();
  }
}
}
}
