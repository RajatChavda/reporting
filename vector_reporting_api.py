from flask import Flask, request, jsonify
from flask_cors import CORS
import json
from vector_reporting import main_f as generate_report_function

# Load configuration
with open("config.json", "r") as file:
    config = json.load(file)

HOST = config.get("host", "127.0.0.1")
PORT = config.get("port", 5000)

api_token = config.get("api_token")

app = Flask(__name__)
CORS(app)

def normalize_to_seconds(timestamp):
    """
    Converts UNIX timestamp in seconds or milliseconds to seconds.
    """
    if timestamp > 1e12:
        return int(timestamp / 1000)
    return int(timestamp)

def verify_api_token(request):
    """ Verifies the API Token from the Authorization header. """
    api_token_header = request.headers.get("Key")
    if not api_token_header:
        return False
    token = api_token_header.strip()
    return token == api_token

@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "Interface Report API is up and running!"}), 200

@app.route("/generate-report", methods=["POST"])
def generate_interface_report():

    if not verify_api_token(request):
        return jsonify({"error": "Invalid or missing API token"}), 401    

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        report_type = data.get("report_type")
        hostname = data.get("hostname")
        from_time_raw = data.get("from_time")
        to_time_raw = data.get("to_time")

        # Early return for availability report
        if report_type == "Avalibility":
            group = data.get("group", [])
            client_group = data.get("client_group", [])

            # Normalize hostname
            if not isinstance(hostname, list):
                if isinstance(hostname, str):
                    cleaned = hostname.strip().strip("{}")
                    hostname = [h.strip() for h in cleaned.split(",") if h.strip()]
                else:
                    hostname = [hostname]

            # Normalize group
            if not isinstance(group, list):
                if isinstance(group, str):
                    cleaned = group.strip().strip("{}")
                    group = [g.strip() for g in cleaned.split(",") if g.strip()]
                else:
                    group = [group]

            # Normalize timestamps
            try:
                from_time = normalize_to_seconds(int(from_time_raw))
                to_time = normalize_to_seconds(int(to_time_raw))
            except (ValueError, TypeError):
                return jsonify({"error": "Invalid time format. Use UNIX timestamp integers."}), 400

            # Email handling
            header_email = request.headers.get("Email")
            raw_emails = data.get("email_list")

            body_emails = []
            if isinstance(raw_emails, list):
                body_emails = raw_emails
            elif isinstance(raw_emails, str):
                cleaned = raw_emails.strip().strip("{}")
                body_emails = [email.strip() for email in cleaned.split(",") if email.strip()]

            to_email = list(set(([header_email] if header_email else []) + body_emails))

            # Call main_t for availability
            return generate_report_function(
                time_from=from_time,
                time_to=to_time,
                report_type=report_type,
                group=group,
                hostname=hostname,
                to_email=to_email if to_email else None,
                client_group=client_group if client_group else None
            )

        metric_name = None
        metrics = []

        if report_type in ("interface", "filesystem"):
            metric_name = data.get("metric_name")
        elif report_type == "Resource":
            metric_name = data.get("metric")

        # Normalize to list if metric_name is a string like "{CPU utilization,CPU idle time}"
        if metric_name:
            if isinstance(metric_name, list):
                metrics = metric_name
            elif isinstance(metric_name, str):
                cleaned = metric_name.strip().strip("{}")
                metrics = [m.strip() for m in cleaned.split(",") if m.strip()]
            else:
                metrics = []

        # Validate required fields
        if report_type == "alert":
            missing_fields = [field for field in ("hostname", "from_time", "to_time") if not data.get(field)]
            if missing_fields:
                return jsonify({"error": f"Missing required fields for alert report: {', '.join(missing_fields)}"}), 400
        else:
            missing_fields = [field for field in ("hostname", "from_time", "to_time", "metric_name" if report_type in ("interface", "filesystem") else "metric") if not data.get(field)]
            if missing_fields:
                return jsonify({"error": f"Missing required fields: {', '.join(missing_fields)}"}), 400

        # Normalize timestamps
        try:
            from_time = normalize_to_seconds(int(from_time_raw))
            to_time = normalize_to_seconds(int(to_time_raw))
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid time format. Use UNIX timestamp integers."}), 400

        user_name = request.headers.get("User", "Unknown")

        # Collect email from header
        header_email = request.headers.get("Email")

        # Get email(s) from JSON body
        raw_emails = data.get("email_list")

        body_emails = []
        if isinstance(raw_emails, list):
            body_emails = raw_emails
        elif isinstance(raw_emails, str):
            cleaned = raw_emails.strip().strip("{}")
            body_emails = [email.strip() for email in cleaned.split(",") if email.strip()]

        to_email = list(set(([header_email] if header_email else []) + body_emails))

        # Call your report generation function
        response = generate_report_function(
            hostname=str(hostname),
            metric_name=metrics,
            time_from=from_time,
            time_to=to_time,
            report_type=str(report_type),
            to_email=to_email if to_email else None,
            user_name=user_name
        )
        return response

    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(debug=True, host=HOST, port=PORT)