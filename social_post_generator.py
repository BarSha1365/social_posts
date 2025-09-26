import sys, os
# sorgt dafür, dass ./src im Suchpfad ist
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from social_post.cli import main

if __name__ == "__main__":
    main()
