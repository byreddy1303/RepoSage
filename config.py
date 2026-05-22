from dotenv import load_dotenv, find_dotenv

# override=True ensures .env values win over empty shell exports
load_dotenv(find_dotenv(), override=True)
