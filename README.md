***Welcome to Assistocrat***

I had the idea to build this when I saw that LEAP71 in Dubai had created an AI engineering tool that had already deigned a very powerful rocket engine. I love aerospace! I was hooked. I learned that their geometry kernel, PicoGK, was open source, so all I had to do was instead of using their proprietary, specialised Noyron AI which cost more than my house to host locally, I could just use the Groq API, right? Wrong. PicoGK is built on C++, and its Python wrappers are terrible. This would give a lot of grief in the backend, in both uses of the term. So I used Meshlib, another open-source community kernel with excellent Python support. I got it working, and then used Reflex Cloud to deploy the app, an advantage of the Reflex framework. I then learned Hack Club gives you free AI credits, and I though I was dreaming when I saw the model selection. 40 minutes of pain later, I finished it, and linked it to my personal site.

A few quick bullet points:
* Uses Gemini 2.5 Flash for low token usage and quick responses
* Uses Meshlib library for advanced geometry
* Not very good at anything past a cube, but should be decent at most basic geometric shapes. If you want more capability, fork the repo and use a more powerful model
* Thank you to Hack Club AI and Stardance for making this possible.

**See You Later!**