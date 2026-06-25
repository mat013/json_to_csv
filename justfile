# Install dependencies
install:
    pip install -r requirement.txt

# Run the Flask development server
run:
    python app.py

# Install dependencies and run
dev: install run

# Install dependencies quietly
install-quiet:
    pip install -q -r requirement.txt

# Run with quiet install
quick: install-quiet run
