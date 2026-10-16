import os

from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402

# Beanstalk busca una variable llamada "application" en application.py
application = create_app()

if __name__ == "__main__":
    application.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=True)
