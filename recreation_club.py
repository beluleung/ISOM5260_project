import pandas as pd
import streamlit as st
import oracledb  # Use python-oracledb instead of cx_Oracle
from datetime import datetime, timedelta
import io
import re  # For input validation

# Streamlit page configuration
st.set_page_config(
    page_title="Club Activity Sign-up",
    page_icon="💪",
    layout="wide",
    )

# Helper function for email validation
def is_valid_email(email):
    pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return re.match(pattern, email)

# Helper function for phone number validation (simple numeric check)
def is_valid_phone(phone):
    """
    Validates phone numbers in the following formats:
    - 123-4567
    - 555-1234
    - 555-123-4567
    - (555) 123-4567
    - 1234567890 (only digits)
    """
    pattern = r'^(\(\d{3}\)\s*|\d{3}[-\.\s]?)?\d{3}[-\.\s]?\d{4}$'
    return re.match(pattern, phone)

# Connection details
HOST_NAME = "imz409.ust.hk"
PORT_NUMBER = "1521"
SERVICE_NAME = "imz409"
USERNAME = "sliangax"
PASSWORD = "3976"


# Function to connect to Oracle Database using python-oracledb in Thin mode
def get_db_connection():
    try:
        # Create a DSN (Data Source Name)
        dsn = oracledb.makedsn(HOST_NAME, PORT_NUMBER, service_name=SERVICE_NAME)

        # Connect to the database using Thin mode (no Oracle Client needed)
        connection = oracledb.connect(
            user=USERNAME,
            password=PASSWORD,
            dsn=dsn,
        )
        return connection
    except oracledb.DatabaseError as e:
        st.error(f"Database connection failed: {str(e)}")
        return None

# Try to connect to the database
connection = get_db_connection()

if connection:
    st.success("Successfully connected to Oracle Database!")
    connection.close()
else:
    st.error("Failed to connect to the database.")


# Member Sign-up Function with Unique Email Validation
def signup_new_member(first_name, last_name, gender, phone, email):
    # Validate user inputs
    if not is_valid_email(email):
        return "Invalid email format."
    if not is_valid_phone(phone):
        return  """
Invalid phone number format. Only one of the following formats are allowed:
    123-4567,
    555-1234,
    555-123-4567,
    (555) 123-4567,
    1234567890 (only digits).
    """

    connection = get_db_connection()
    if not connection:
        return "Database connection failed."

    cursor = connection.cursor()

    try:
        # Step 1: Check for existing email (unique email constraint)
        cursor.execute("SELECT COUNT(*) FROM Member WHERE email = :email", email=email)
        if cursor.fetchone()[0] > 0:
            return "A member with this email already exists. Please use a different email."

        # Step 2: Find the current maximum memberid in the Member table
        cursor.execute("SELECT MAX(memberid) FROM Member")
        max_memberid = cursor.fetchone()[0]  # Fetch the max memberid

        if max_memberid is None:
            max_memberid = 0  # If no members exist, set max_memberid to 0

        # Step 3: Get the current next value of the member_seq sequence
        cursor.execute("SELECT member_seq.NEXTVAL FROM dual")
        current_seq_value = cursor.fetchone()[0]  # Fetch the next sequence value

        # Step 4: If the sequence is behind, restart it with a value higher than max_memberid
        if current_seq_value <= max_memberid:
            new_value = max_memberid + 1
            cursor.execute(f"ALTER SEQUENCE member_seq RESTART START WITH {new_value}")
            connection.commit()  # Commit the sequence adjustment

        # Step 5: Automatically calculate join_date, expire_date, and set status to 'active'
        join_date = datetime.now()
        expire_date = datetime.now() + timedelta(days=365)  # Expire in 1 year
        status = 'active'

        # Step 6: Insert the new member into the Members table using the adjusted sequence
        cursor.execute("""
            INSERT INTO Member (memberid, first_name, last_name, gender, phone, email, join_date, expire_date, status)
            VALUES (member_seq.NEXTVAL, :first_name, :last_name, :gender, :phone, :email, :join_date, :expire_date, :status)
        """, first_name=first_name, last_name=last_name, gender=gender, phone=phone, email=email, join_date=join_date, expire_date=expire_date, status=status)

        # Commit the transaction
        connection.commit()

    except Exception as e:
        return f"Failed to sign up new member: {e}"

    finally:
        # Close the cursor and connection
        cursor.close()
        connection.close()

    return "New member successfully signed up!"

# Activity Sign-up Function with Validation
def signup_for_activity(member_name, email, activity_id):
    # Validate inputs
    if not is_valid_email(email):
        return "Invalid email format."

    connection = get_db_connection()
    if not connection:
        return "Database connection failed."

    cursor = connection.cursor()

    try:
        # Step 1: Check if the member exists
        cursor.execute("SELECT memberid FROM Member WHERE email = :email", email=email)
        member = cursor.fetchone()

        if member:
            member_id = member[0]
            signup_date = datetime.now()

            # Step 2: Find the current maximum signupid in the SignUp table
            cursor.execute("SELECT MAX(signupid) FROM SignUp")
            max_signupid = cursor.fetchone()[0]

            if max_signupid is None:
                max_signupid = 0  # If no signups exist, set max_signupid to 0

            # Step 3: Get the current next value of the signups_seq sequence
            cursor.execute("SELECT signups_seq.NEXTVAL FROM dual")
            current_seq_value = cursor.fetchone()[0]

            # Step 4: If the sequence is behind, restart it with a value higher than max_signupid
            if current_seq_value <= max_signupid:
                new_value = max_signupid + 1
                cursor.execute(f"ALTER SEQUENCE signups_seq RESTART START WITH {new_value}")
                connection.commit()  # Commit the sequence adjustment

            # Step 5: Insert the new sign-up into the SignUp table using the adjusted sequence
            cursor.execute("""
                INSERT INTO SignUp (signupid, memberid, activityid, signup_date)
                VALUES (signups_seq.NEXTVAL, :member_id, :activity_id, :signup_date)
            """, member_id=member_id, activity_id=activity_id, signup_date=signup_date)

            # Commit the transaction
            connection.commit()

            return f"{member_name} has successfully signed up for activity {activity_id}!"
        else:
            return "Member not found. Please sign up first."

    except Exception as e:
        return f"Failed to sign up for activity: {e}"

    finally:
        # Close the cursor and connection
        cursor.close()
        connection.close()

# Function to browse all activities and display in a table
def browse_activities():
    st.write("Attempting to fetch activities...")  # Add a log to ensure this function is triggered

    connection = get_db_connection()
    if connection is None:
        st.error("Failed to connect to the database.")
        return None

    try:
        cursor = connection.cursor()

        query = """
        SELECT a.activityname, a.activity_date, a.start_time, a.end_time, a.location, a.price,
               i.first_name || ' ' || i.last_name AS instructor
        FROM Activity a
        JOIN InstructorActivity ia ON a.activityid = ia.activityid
        JOIN Instructor i ON ia.instructorid = i.instructorid
        ORDER BY a.activity_date
        """
        cursor.execute(query)

        # Fetch raw data
        activities = cursor.fetchall()

        if not activities:
            st.warning("No activities found.")
            return None

        # Process the data to convert datetime to just time (HH:MM)
        processed_activities = []
        for activity in activities:
            activity_name, activity_date, start_time, end_time, location, price, instructor = activity

            # Convert start_time and end_time to HH:MM format
            start_time_str = start_time.strftime("%H:%M")  # Format time part only
            end_time_str = end_time.strftime("%H:%M")      # Format time part only

            # Append the processed data
            processed_activities.append((activity_name, activity_date, start_time_str, end_time_str, location, price, instructor))

        # Convert the result to a pandas DataFrame
        columns = ['Activity Name', 'Date', 'Start Time', 'End Time', 'Location', 'Price', 'Instructor']
        activities_df = pd.DataFrame(processed_activities, columns=columns)

        cursor.close()
        connection.close()

        return activities_df

    except Exception as e:
        st.error(f"Error fetching activities: {str(e)}")
        return None

# Admin Report Function
def generate_signup_report():
    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT m.first_name || ' ' || m.last_name, a.activityname, s.signup_date
        FROM SignUp s
        JOIN Member m ON s.memberid = m.memberid
        JOIN Activity a ON s.activityid = a.activityid
        ORDER BY s.signup_date
    """)

    report_data = cursor.fetchall()
    cursor.close()
    connection.close()

    return report_data

# Admin SQL Query Function
def execute_custom_query(query):
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # Execute the query
        cursor.execute(query)
        data = cursor.fetchall()

        # Get the column names from the cursor and create the DataFrame
        columns = [col[0] for col in cursor.description]  # Fetch column headers
        query_data = pd.DataFrame(data, columns=columns)

    except Exception as e:
        # Handle any errors that occur during query execution
        query_data = pd.DataFrame()  # Return an empty DataFrame on error
        print(f"An error occurred: {e}")

    finally:
        # Always close the cursor and connection
        cursor.close()
        connection.close()

    return query_data


# Streamlit App Layout
def main():
    # Adding a banner image
    st.image("https://images.unsplash.com/photo-1588286840104-8957b019727f?q=80&w=2940&auto=format&fit=crop&ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D", use_column_width=True)  # Replace with your own image URL

    st.title("Activity Sign-up System")

    # Sidebar Menu with Submenus
    st.sidebar.title("Navigation")
    section = st.sidebar.radio("Main Menu", ["Member", "Admin"])

    if section == "Member":
        st.sidebar.subheader("Member Options")
        member_menu = st.sidebar.radio("Select Option", ["New Member Sign-up","Browse Activities", "Activity Sign-up"])

        if member_menu == "New Member Sign-up":
            st.subheader("New Member Sign-up")
            # Member sign-up form with new fields
            first_name = st.text_input("First Name")
            last_name = st.text_input("Last Name")
            gender = st.selectbox("Gender", ("M", "F"))
            phone = st.text_input("Phone Number")
            email = st.text_input("Email")
            if st.button("Sign Up"):
                if first_name and last_name and gender and phone and email:
                    result = signup_new_member(first_name, last_name, gender, phone, email)
                    st.success(result)
                else:
                    st.warning("Please fill all fields!")

        elif member_menu == "Activity Sign-up":
            st.subheader("Activity Sign-up")
            member_name = st.text_input("Enter your Name")
            email = st.text_input("Enter your Email")
            activity_id = st.text_input("Enter Activity ID")
            if st.button("Sign Up"):
                if member_name and email and activity_id:
                    result = signup_for_activity(member_name, email, activity_id)
                    st.success(result)
                else:
                    st.warning("Please fill all fields!")

        elif member_menu == "Browse Activities":
            st.subheader("Browse Activities")
            activities_df = browse_activities()
            if activities_df is not None:
                st.write("**Available Activities:**")
                st.dataframe(activities_df)  # Display the activities in a table format
            else:
                st.warning("No activities found.")

    elif section == "Admin":
        st.sidebar.subheader("Admin Options")
        admin_menu = st.sidebar.radio("Select Admin Option", ["Generate Reports", "Data"])

        if admin_menu == "Generate Reports":
            st.subheader("Admin: Generate Signup Report")

            if st.button("Generate Report"):
                report_data = generate_signup_report()
                if report_data:
                    st.write("**Signup Report:**")
                    for row in report_data:
                        st.write(f"{row[0]} signed up for {row[1]} on {row[2]}")
                else:
                    st.warning("No signup data available.")

        elif admin_menu == "Data":
            st.subheader("Admin: Run SQL Queries")

            query = st.text_area("Enter your SQL query")
            if st.button("Execute Query"):
                if query.strip().lower().startswith("select"):
                    try:
                        results = execute_custom_query(query)
                        if not results.empty:
                            st.write("**Query Results:**")
                            st.dataframe(results)  # Display the query results


                            # Convert DataFrame to CSV and Excel formats
                            csv_data = results.to_csv(index=False).encode('utf-8')

                            # Use io.BytesIO to store Excel data in memory
                            with io.BytesIO() as buffer:
                                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                                    results.to_excel(writer, index=False)
                                excel_data = buffer.getvalue()

                            # Download button for CSV
                            st.download_button(
                                label="Download as CSV",
                                data=csv_data,
                                file_name='query_result.csv',
                                mime='text/csv'
                            )

                            # Download button for Excel
                            st.download_button(
                                label="Download as Excel",
                                data=excel_data,
                                file_name='query_result.xlsx',
                                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                            )
                        else:
                            st.warning("Query returned no results.")
                    except Exception as e:
                        st.error(f"An error occurred: {e}")
                else:
                    st.error("Only SELECT queries are allowed for safety.")

if __name__ == "__main__":
    main()
