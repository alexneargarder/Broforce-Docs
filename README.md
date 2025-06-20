# Broforce Modding Documentation

This repo provides XML documentation for some of Broforce's classes. 
The vast majority of the documentation was generated automatically by having an AI analyze the game's code and write documentation based on its understanding of the code, so it's possible there will be some mistakes. In general it seems to be fairly accurate from what I've been able to review so far, but I would advise against completely trusting it and reviewing the code yourself if you doubt what it says. <br> <br>
If you do find any mistakes, I would greatly appreciate if you took the time to correct it, and submitted a pull request with your changes.

## Using the Documentation

The main documentation file is `Assembly-CSharp.xml` in the root directory. To use it with dnSpy or Visual Studio:

- Place the `Assembly-CSharp.xml` file in the same directory as your `Assembly-CSharp.dll` file
- The documentation will then appear as tooltips when hovering over classes and methods

You can also browse the documentation on this repo's GitHub wiki, which contains all the same information as the XML files.

Individual class documentation is available in the `Classes/` directory as well.

## Contributing

To contribute or improve documentation:

1. Edit the individual class XML files in the `Classes/` directory
2. Run `python3 Scripts/build-documentation.py` to regenerate `Assembly-CSharp.xml` (if you have trouble with the script not working, feel free to skip this and I can rebuild it myself)
3. Create a pull request (or if you plan on making frequent changes I can add you as a contributor so you make commits to the repo directly)

**Note:** Don't edit `Assembly-CSharp.xml` directly - it's automatically generated from the individual class files.