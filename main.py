#!/usr/bin/env python3
"""
Food Donation Chatbot - v3 with Detailed Contacts and Separate Logging
A conversational AI assistant to help connect food donors with recipients and log requests.
"""

import json
import time
import os
import re
import sys


# --- PACKAGE IMPORTS AND CHECKS ---
def check_and_install_packages():
    """Check if required packages are installed and provide installation instructions."""
    # ... (This function remains unchanged, so it's omitted for brevity) ...
    # Re-import to ensure they are in the global scope
    try:
        import googlemaps
        import gspread
        from oauth2client.service_account import ServiceAccountCredentials
        from langchain_core.tools import tool
        from langgraph.prebuilt import create_react_agent
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage
        print("✅ All packages imported successfully.")
        return googlemaps, gspread, ServiceAccountCredentials, tool, create_react_agent, ChatGoogleGenerativeAI, HumanMessage
    except ImportError:
        print("❌ Critical packages are missing. Please install them.")
        sys.exit(1)


googlemaps, gspread, ServiceAccountCredentials, tool, create_react_agent, ChatGoogleGenerativeAI, HumanMessage = check_and_install_packages()


# --- TOOL DEFINITIONS ---

@tool
def find_recipients(location: str) -> str:
    """
    Searches for food banks and charities near a location, then gets detailed contact
    information (phone, website) for each one.

    Args:
        location: The address, city, or ZIP code to search around.

    Returns:
        A JSON string of potential recipients with their details.
    """
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return json.dumps({"error": "Google API key not found."})

    gmaps = googlemaps.Client(key=api_key)
    try:
        geocode_result = gmaps.geocode(location)
        if not geocode_result:
            return json.dumps({"error": f"Could not find coordinates for '{location}'"})

        lat_lng = geocode_result[0]['geometry']['location']
        places_result = gmaps.places_nearby(
            location=lat_lng, radius=8000, keyword='food bank OR charity OR food donation'
        )

        detailed_recipients = []
        for place in places_result.get('results', [])[:5]:
            place_id = place.get('place_id')
            if not place_id:
                continue

            # Get detailed info for each place
            details = gmaps.place(
                place_id=place_id,
                fields=['name', 'vicinity', 'formatted_phone_number', 'website', 'rating']
            )
            place_details = details.get('result', {})

            detailed_recipients.append({
                "name": place_details.get('name', 'N/A'),
                "address": place_details.get('vicinity', 'N/A'),
                "phone": place_details.get('formatted_phone_number', 'Not available'),
                "website": place_details.get('website', 'Not available'),
                "rating": place_details.get('rating', 'N/A'),
            })
            time.sleep(0.05)  # Small delay to be respectful to the API

        if detailed_recipients:
            return json.dumps({"recipients": detailed_recipients})
        else:
            return json.dumps({"message": "No organizations found via Google Places API."})
    except Exception as e:
        return json.dumps({"api_error": True, "error": str(e)})


@tool
def log_donation_request(user_name: str, user_phone: str, organizations_json: str) -> str:
    """
    Logs a food donation request to a Google Sheet. It creates a separate row for each
    NGO, pairing it with the donor's information.

    Args:
        user_name: The name of the donor.
        user_phone: The phone number of the donor.
        organizations_json: A JSON string of the organizations that were found.

    Returns:
        A confirmation or error message as a JSON string.
    """
    if not gspread:
        return json.dumps({"error": "gspread library not available. Cannot log to sheet."})

    spreadsheet_id = os.environ.get("GOOGLE_SHEET_ID")
    if not spreadsheet_id:
        return json.dumps({"error": "GOOGLE_SHEET_ID environment variable not set."})

    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(spreadsheet_id).sheet1

        organizations = json.loads(organizations_json)
        timestamp = time.ctime()
        rows_to_add = []

        for org in organizations:
            row = [
                user_name,
                user_phone,
                org.get('name', 'N/A'),
                org.get('phone', 'N/A'),
                org.get('website', 'N/A'),
                timestamp
            ]
            rows_to_add.append(row)

        # Add headers if sheet is empty
        if not sheet.get_all_values():
            sheet.append_row(["Donor Name", "Donor Phone", "NGO Name", "NGO Phone", "NGO Website", "Timestamp"])

        # Append all rows in a single API call for efficiency
        if rows_to_add:
            sheet.append_rows(rows_to_add)

        return json.dumps({"success": True, "message": "Request logged successfully in the Google Sheet."})

    except FileNotFoundError:
        return json.dumps(
            {"error": "service_account.json not found. Please ensure the file is in the correct directory."})
    except Exception as e:
        return json.dumps({"error": f"An error occurred while writing to the sheet: {str(e)}"})


# --- MAIN CHATBOT CLASS ---
class FoodDonationChatbot:
    def __init__(self):
        self.agent_executor = None
        self.conversation_context = {}
        self.cached_organizations = []
        self.setup_agent()

    def setup_agent(self):
        """Initializes the LangChain agent."""
        # ... (This function remains unchanged) ...
        try:
            api_key = os.environ.get("GOOGLE_API_KEY")
            llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.2, google_api_key=api_key)
            tools = [find_recipients, log_donation_request]
            self.agent_executor = create_react_agent(llm, tools=tools)
            print("✅ Agent setup complete.")
        except Exception as e:
            print(f"⚠️ Agent setup failed: {e}")

    def format_organizations(self, orgs_data):
        """Formats the organization data for display."""
        if not orgs_data:
            return "No organizations found."
        response = ""
        for i, org in enumerate(orgs_data, 1):
            response += f"🏢 **{i}. {org['name']}**\n"
            response += f"   📍 Address: {org.get('address', 'N/A')}\n"
            response += f"   📞 Phone: {org.get('phone', 'Not available')}\n"
            response += f"   🌐 Website: {org.get('website', 'Not available')}\n"
        return response

    def process_message(self, message):
        """Processes the user's message and manages the conversation flow."""
        # ... (This function remains unchanged from the previous fix) ...
        message_lower = message.lower().strip()

        if self.conversation_context.get('awaiting_user_name'):
            self.conversation_context['user_name'] = message
            self.conversation_context['awaiting_user_name'] = False
            self.conversation_context['awaiting_user_phone'] = True
            return "Thank you. Now, what is your phone number?"

        if self.conversation_context.get('awaiting_user_phone'):
            self.conversation_context['user_phone'] = message
            self.conversation_context['awaiting_user_phone'] = False

            user_name = self.conversation_context.get('user_name')
            user_phone = self.conversation_context.get('user_phone')
            orgs_json = json.dumps(self.cached_organizations)

            print("\n⚙️ Logging your request to Google Sheets...")
            log_result_str = log_donation_request.invoke({
                "user_name": user_name,
                "user_phone": user_phone,
                "organizations_json": orgs_json
            })
            log_result = json.loads(log_result_str)

            self.conversation_context.clear()

            if log_result.get('success'):
                return f"✅ {log_result['message']}"
            else:
                return f"❌ Error: {log_result['error']}"

        if self.conversation_context.get('awaiting_log_confirmation'):
            if message_lower == 'yes':
                self.conversation_context['awaiting_log_confirmation'] = False
                self.conversation_context['awaiting_user_name'] = True
                return "Great! To proceed, please provide your name."
            else:
                self.conversation_context.clear()
                return "Okay, I will not log this request. Is there anything else I can help you with?"

        if "find" in message_lower or "donate" in message_lower or "where can" in message_lower:
            self.cached_organizations = []
            print("\n🔄 Searching for organizations...")

            location_match = re.search(r'in\s(.+)', message, re.IGNORECASE)
            if not location_match:
                return "I can help with that! Please tell me the city you are in, for example: 'I want to donate in Delhi'."

            location = location_match.group(1).strip()
            result_str = find_recipients.invoke(location)
            result_data = json.loads(result_str)

            if "recipients" in result_data and result_data["recipients"]:
                self.cached_organizations = result_data["recipients"]
                response = f"✅ I found these organizations in {location}:\n\n"
                response += self.format_organizations(self.cached_organizations)
                response += "\n\n📝 **Would you like me to log this request with these organizations for you? (yes/no)**"

                self.conversation_context['awaiting_log_confirmation'] = True
                return response
            else:
                return f"I'm sorry, I couldn't find any organizations. Error: {result_data.get('error', 'Unknown issue')}"

        return "I can help you find food donation centers. Please tell me what city you're in, like 'Where can I donate food in Delhi?'"

    def run_chat(self):
        """Main chat loop."""
        # ... (This function remains unchanged) ...
        print("🍽️" + "═" * 50 + "🍽️")
        print("     🤖 Food Donation & Logging Assistant (v3)")
        print("🍽️" + "═" * 50 + "🍽️")
        print("\n🤗 Hello! I can find local organizations for your food donations and log the request for you.")
        print('   Example: "I want to donate food in New Delhi"')

        while True:
            try:
                user_input = input("\n💬 You: ").strip()
                if user_input.lower() in ['quit', 'exit', 'bye']:
                    print("\n🙏 Thank you! Goodbye!")
                    break

                print("\n🤖 Assistant: ", end="")
                response = self.process_message(user_input)
                print(response)

            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ An unexpected error occurred: {e}")
                self.conversation_context.clear()


# --- MAIN EXECUTION ---
def main():
    """Main function to run the chatbot."""
    # ... (This function remains unchanged) ...
    if not os.environ.get("GOOGLE_API_KEY"):
        print("⚠️ WARNING: GOOGLE_API_KEY environment variable not set. Searches will fail.")
    if not os.environ.get("GOOGLE_SHEET_ID"):
        print("⚠️ WARNING: GOOGLE_SHEET_ID environment variable not set. Logging to sheet will fail.")
    if not os.path.exists("service_account.json"):
        print("⚠️ WARNING: 'service_account.json' not found. Logging to sheet will fail.")

    chatbot = FoodDonationChatbot()
    chatbot.run_chat()


if __name__ == "__main__":
    main()