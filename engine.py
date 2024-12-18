from flask import Flask, render_template, request, redirect, flash, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor
import secrets  # For generating a secret key

app = Flask(__name__)

# Set a unique secret key for session handling
app.secret_key = secrets.token_hex(16)

# Database configuration
db_config = {
    'dbname': 'steps_activities',
    'user': 'postgres',
    'password': '1234',
    'host': 'localhost',
    'port': '5432'
}

# Helper function: Fetch activities from steps_conversion_chart_data
def get_activities():
    try:
        with psycopg2.connect(**db_config) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("SELECT activity FROM steps_conversion_chart_data")
                activities = [row['activity'] for row in cursor.fetchall()]
        return activities
    except Exception as e:
        print(f"Error fetching activities: {e}")
        return []

# Helper function: Fetch existing usernames from user_activity_log
def get_existing_usernames():
    try:
        with psycopg2.connect(**db_config) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT DISTINCT username FROM user_activity_log")
                usernames = [row[0] for row in cursor.fetchall()]
        return usernames
    except Exception as e:
        print(f"Error fetching usernames: {e}")
        return []

# Route: Home page with form
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        return log_activity()

    activities = get_activities()
    usernames = get_existing_usernames()
    return render_template('index.html', activities=activities, usernames=usernames)

# Route: Log activity
@app.route('/log_activity', methods=['POST'])
def log_activity():
    entry_date = request.form['entry_date']
    username = request.form.get('username') or request.form.get('new-username')

    if not username:
        flash('Username is required.', 'error')
        return redirect('/')

    activity = request.form['activity']
    entered_minutes = int(request.form['entered_minutes'])

    try:
        with psycopg2.connect(**db_config) as conn:
            with conn.cursor() as cursor:
                # Fetch steps_min for the selected activity
                cursor.execute(
                    "SELECT steps_min FROM steps_conversion_chart_data WHERE activity = %s",
                    (activity,)
                )
                result = cursor.fetchone()

                if result:
                    steps_min = result[0]
                    total_steps = steps_min * entered_minutes

                    # Insert activity log into user_activity_log
                    cursor.execute(
                        """
                        INSERT INTO user_activity_log (entry_date, username, activity, steps_count)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (entry_date, username, activity, total_steps)
                    )
                    conn.commit()
                    flash('Activity logged successfully!', 'success')
                else:
                    flash('Invalid activity selected!', 'error')
    except Exception as e:
        print(f"Error logging activity: {e}")
        flash('Error logging activity. Please try again.', 'error')

    return redirect('/')

# Route: Get top users for the last 7 days
@app.route('/top_users', methods=['GET'])
def top_users():
    try:
        with psycopg2.connect(**db_config) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT 
                        TRIM(username) AS username, 
                        entry_date::date AS date, 
                        SUM(steps_count) AS total_steps
                    FROM user_activity_log
                    WHERE entry_date >= NOW() - INTERVAL '7 days'
                    GROUP BY TRIM(username), entry_date::date
                    ORDER BY entry_date ASC, username ASC
                """)
                activity_data = cursor.fetchall()

        # Prepare data for the chart
        users_data = {}
        dates = []

        for entry in activity_data:
            username = entry['username']
            date = entry['date']
            total_steps = entry['total_steps']

            if date not in dates:
                dates.append(date)

            if username not in users_data:
                users_data[username] = {date: total_steps}
            else:
                users_data[username][date] = total_steps

        # Ensure each user has an entry for every date
        for username in users_data:
            for date in dates:
                if date not in users_data[username]:
                    users_data[username][date] = 0

        # Prepare data for frontend
        chart_data = {
            'dates': [str(date) for date in dates],
            'usernames': list(users_data.keys()),
            'steps_data': [
                [users_data[username].get(date, 0) for date in dates]
                for username in users_data
            ]
        }

        return jsonify(chart_data)

    except Exception as e:
        print(f"Error fetching top users: {e}")
        return jsonify({'error': 'Error fetching data'}), 500
    
# Route: Weekly Winner and Loser
@app.route('/weekly_summary', methods=['GET'])
def weekly_summary():
    try:
        with psycopg2.connect(**db_config) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT 
                        TRIM(username) AS username,
                        SUM(steps_count) AS total_steps
                    FROM user_activity_log
                    WHERE entry_date >= NOW() - INTERVAL '7 days'
                    GROUP BY TRIM(username)
                    ORDER BY total_steps DESC
                """)
                summary_data = cursor.fetchall()

        if summary_data:
            winner = summary_data[0]
            loser = summary_data[-1]

            result = {
                'winner': {
                    'username': winner['username'],
                    'steps': winner['total_steps']
                },
                'loser': {
                    'username': loser['username'],
                    'steps': loser['total_steps']
                }
            }
        else:
            result = {
                'winner': None,
                'loser': None
            }

        return jsonify(result)

    except Exception as e:
        print(f"Error fetching weekly summary: {e}")
        return jsonify({'error': 'Error fetching weekly summary'}), 500

    

# Run the application
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=True, use_reloader=False)
