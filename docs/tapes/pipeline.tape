# VHS tape: pipeline inspection demo
# Run: vhs docs/tapes/pipeline.tape

Output docs/public/demos/pipeline.gif
Output docs/public/demos/pipeline.webm

Set Shell "bash"
Set FontSize 14
Set Width 900
Set Height 600
Set Theme "Catppuccin Mocha"
Set Padding 20
Set TypingSpeed 50ms

Type "rdc open hello_triangle.rdc"
Enter
Sleep 1.5s

Type "rdc pipeline 5"
Enter
Sleep 2.5s

Type "rdc bindings 5"
Enter
Sleep 2s

Type "rdc resources --type texture --sort size"
Enter
Sleep 2s

Type "rdc ls /draws/5/"
Enter
Sleep 2s

Type "rdc cat /draws/5/pipeline/shader/vs"
Enter
Sleep 3s

Type "rdc close"
Enter
Sleep 1s
