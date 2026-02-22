# VHS tape: quickstart demo
# Run: vhs docs/tapes/quickstart.tape

Output docs/public/demos/quickstart.gif
Output docs/public/demos/quickstart.webm

Set Shell "bash"
Set FontSize 14
Set Width 900
Set Height 500
Set Theme "Catppuccin Mocha"
Set Padding 20
Set TypingSpeed 50ms

Type "rdc open hello_triangle.rdc"
Enter
Sleep 1.5s

Type "rdc info"
Enter
Sleep 2s

Type "rdc draws"
Enter
Sleep 2s

Type "rdc pipeline 5 --section shader --json | jq '.ps.entryPoint'"
Enter
Sleep 2s

Type "rdc shader 5 ps | head -20"
Enter
Sleep 3s

Type "rdc close"
Enter
Sleep 1s
