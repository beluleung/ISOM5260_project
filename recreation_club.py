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

# Oracle Database Connection Details
HOST_NAME = "imz409.ust.hk"
PORT_NUMBER = "1521"
SERVICE_NAME = "imz409"
USERNAME = "sliangax"
PASSWORD = "3976"

# Function to connect to Oracle Database using python-oracledb in Thin mode
def get_db_connection():
    try:
        dsn = oracledb.makedsn(HOST_NAME, PORT_NUMBER, service_name=SERVICE_NAME)
        connection = oracledb.connect(user=USERNAME, password=PASSWORD, dsn=dsn)
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
        return  "Invalid phone number format. Only the following phone number formats are allowed: 123-4567, 555-1234, 555-123-4567, (555) 123-4567, 1234567890 (only digits)."


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
    if not is_valid_email(email):
        return "Invalid email format."

    connection = get_db_connection()
    if not connection:
        return "Database connection failed."

    cursor = connection.cursor()

    try:
        cursor.execute("SELECT memberid FROM Member WHERE email = :email", email=email)
        member = cursor.fetchone()

        if member:
            member_id = member[0]
            signup_date = datetime.now()

            cursor.execute("SELECT MAX(signupid) FROM SignUp")
            max_signupid = cursor.fetchone()[0]
            if max_signupid is None:
                max_signupid = 0

            cursor.execute("SELECT signups_seq.NEXTVAL FROM dual")
            current_seq_value = cursor.fetchone()[0]

            if current_seq_value <= max_signupid:
                new_value = max_signupid + 1
                cursor.execute(f"ALTER SEQUENCE signups_seq RESTART START WITH {new_value}")
                connection.commit()

            cursor.execute("""
                INSERT INTO SignUp (signupid, memberid, activityid, signup_date)
                VALUES (signups_seq.NEXTVAL, :member_id, :activity_id, :signup_date)
            """, member_id=member_id, activity_id=activity_id, signup_date=signup_date)

            connection.commit()
            return f"{member_name} has successfully signed up for activity {activity_id}!"
        else:
            return "Member not found. Please sign up first."

    except Exception as e:
        return f"Failed to sign up for activity: {e}"

    finally:
        cursor.close()
        connection.close()

# Function to browse all activities and display in a table
def browse_activities():
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
        activities = cursor.fetchall()

        if not activities:
            st.warning("No activities found.")
            return None

        processed_activities = []
        for activity in activities:
            activity_name, activity_date, start_time, end_time, location, price, instructor = activity
            activity_date_str = activity_date.strftime("%Y-%m-%d")
            start_time_str = start_time.strftime("%H:%M")
            end_time_str = end_time.strftime("%H:%M")
            processed_activities.append((activity_name, activity_date_str, start_time_str, end_time_str, location, price, instructor))

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
        cursor.execute(query)
        data = cursor.fetchall()
        if not data:
            return None

        columns = [col[0] for col in cursor.description]
        query_data = pd.DataFrame(data, columns=columns)

    except Exception as e:
        query_data = None
        st.error(f"An error occurred while executing the query: {e}")

    finally:
        cursor.close()
        connection.close()

    return query_data

# Function to create a new activity in the database
def create_activity(activity_name, activity_date, start_time, end_time, location, price):
    connection = get_db_connection()
    if not connection:
        return "Database connection failed."

    cursor = connection.cursor()

    try:
        # Step 1: Find the current maximum activityid
        cursor.execute("SELECT MAX(activityid) FROM Activity")
        max_activityid = cursor.fetchone()[0] or 0  # Default to 0 if no activities exist

        # Step 2: Get the current next value of the activity_seq sequence
        cursor.execute("SELECT activity_seq.NEXTVAL FROM dual")
        current_seq_value = cursor.fetchone()[0]

        # Step 3: If the sequence is behind, restart it with a value higher than max_activityid
        if current_seq_value <= max_activityid:
            new_value = max_activityid + 1
            cursor.execute(f"ALTER SEQUENCE activity_seq RESTART START WITH {new_value}")
            connection.commit()  # Commit the sequence adjustment

            # Get the next value after restarting
            cursor.execute("SELECT activity_seq.NEXTVAL FROM dual")
            current_seq_value = cursor.fetchone()[0]

        # Step 4: Insert the new activity into the Activity table using the adjusted sequence
        cursor.execute("""
            INSERT INTO Activity (activityid, activityname, activity_date, start_time, end_time, location, price)
            VALUES (:activity_id, :activity_name, :activity_date, :start_time, :end_time, :location, :price)
        """, activity_id=current_seq_value, activity_name=activity_name, activity_date=activity_date,
           start_time=start_time, end_time=end_time, location=location, price=price)

        connection.commit()
        return f"Activity '{activity_name}' created successfully!"

    except Exception as e:
        return f"Failed to create activity: {e}"

    finally:
        cursor.close()
        connection.close()

# Function to update an existing activity
def update_activity(activity_id, activity_name, activity_date, start_time, end_time, location, price):
    connection = get_db_connection()
    if not connection:
        return "Database connection failed."

    cursor = connection.cursor()

    try:
        cursor.execute("""
            UPDATE Activity
            SET activityname = :activity_name, activity_date = :activity_date, start_time = :start_time,
                end_time = :end_time, location = :location, price = :price
            WHERE activityid = :activity_id
        """, activity_name=activity_name, activity_date=activity_date, start_time=start_time,
        end_time=end_time, location=location, price=price, activity_id=activity_id)

        connection.commit()
        return f"Activity '{activity_name}' updated successfully!"

    except Exception as e:
        return f"Failed to update activity: {e}"

    finally:
        cursor.close()
        connection.close()

# Function to check for dependencies before attempting to delete an activity
def has_child_records(activity_id):
    connection = get_db_connection()
    if not connection:
        return True  # Treat as having child records if connection fails

    cursor = connection.cursor()
    try:
        # Check for any related records in "SIGNUP" table
        cursor.execute("SELECT COUNT(*) FROM SIGNUP WHERE activity_id = :activity_id", activity_id=activity_id)
        count = cursor.fetchone()[0]
        return count > 0  # Return True if there are child records
    except Exception as e:
        # Log the error or handle it accordingly
        print(f"Error checking for child records: {e}")
        return True  # Treat as having child records if an error occurs
    finally:
        cursor.close()
        connection.close()

# Function to delete an activity
def delete_activity(activity_id):
    connection = get_db_connection()
    if not connection:
        return "Database connection failed."

    cursor = connection.cursor()

    try:
        cursor.execute("DELETE FROM Activity WHERE activityid = :activity_id", activity_id=activity_id)
        connection.commit()
        return "Activity deleted successfully!"

    except Exception as e:
        return f"Failed to delete activity: {e}"

    finally:
        cursor.close()
        connection.close()

# Function to fetch all activities for editing or deletion
def fetch_all_activities():
    connection = get_db_connection()
    if not connection:
        return None

    cursor = connection.cursor()

    try:
        cursor.execute("SELECT activityid, activityname FROM Activity ORDER BY activityname")
        activities = cursor.fetchall()
        return activities

    except Exception as e:
        st.error("Failed to fetch activities.")
        return None

    finally:
        cursor.close()
        connection.close()

# Streamlit Admin Menu for Managing Activities
def manage_activities():
    st.subheader("Admin: Manage Activities")

    # Tabs for creating, editing, or deleting activities
    tabs = st.tabs(["Create Activity", "Edit Activity", "Delete Activity"])

    # Tab 1: Create Activity
    with tabs[0]:
        st.subheader("Create a New Activity")
        # Add keys to ensure unique IDs
        activity_name = st.text_input("Activity Name", key="create_activity_name")
        activity_date = st.date_input("Activity Date", key="create_activity_date")
        start_time = st.time_input("Start Time", key="create_start_time")
        end_time = st.time_input("End Time", key="create_end_time")
        location = st.text_input("Location", key="create_location")
        price = st.number_input("Price", min_value=0.0, format="%.2f", key="create_price")

        if st.button("Create Activity", key="create_activity_button"):
            if activity_name and location and price >= 0:
                start_time_str = start_time.strftime("%H:%M:%S")
                end_time_str = end_time.strftime("%H:%M:%S")
                result = create_activity(activity_name, activity_date, start_time_str, end_time_str, location, price)
                st.success(result)
            else:
                st.warning("Please fill in all the fields correctly.")

    # Tab 2: Edit Activity
    with tabs[1]:
        st.subheader("Edit an Existing Activity")
        activities = fetch_all_activities()
        if activities:
            activity_map = {f"{name} (ID: {id})": id for id, name in activities}
            activity_choice = st.selectbox("Select an Activity to Edit", list(activity_map.keys()), key="edit_activity_choice")
            activity_id = activity_map[activity_choice]

            # Add keys to ensure unique IDs
            activity_name = st.text_input("Activity Name", key="edit_activity_name")
            activity_date = st.date_input("Activity Date", key="edit_activity_date")
            start_time = st.time_input("Start Time", key="edit_start_time")
            end_time = st.time_input("End Time", key="edit_end_time")
            location = st.text_input("Location", key="edit_location")
            price = st.number_input("Price", min_value=0.0, format="%.2f", key="edit_price")

            if st.button("Update Activity", key="update_activity_button"):
                if activity_name and location and price >= 0:
                    start_time_str = start_time.strftime("%H:%M:%S")
                    end_time_str = end_time.strftime("%H:%M:%S")
                    result = update_activity(activity_id, activity_name, activity_date, start_time_str, end_time_str, location, price)
                    st.success(result)
                else:
                    st.warning("Please fill in all the fields correctly.")
        else:
            st.warning("No activities found.")

    # Tab 3: Delete Activity
    with tabs[2]:
        st.subheader("Delete an Activity")
        activities = fetch_all_activities()
        if activities:
            activity_map = {f"{name} (ID: {id})": id for id, name in activities}
            activity_choice = st.selectbox("Select an Activity to Delete", list(activity_map.keys()), key="delete_activity_choice")
            activity_id = activity_map[activity_choice]

            if st.button("Delete Activity", key="delete_activity_button"):
                if not has_child_records(activity_id):
                    result = delete_activity(activity_id)
                    st.success(result)
                else:
                    st.warning("Cannot delete this activity because it has associated records.")
        else:
            st.warning("No activities found.")

# Streamlit App Layout
def main():
    st.image("https://images.unsplash.com/photo-1588286840104-8957b019727f?q=80&w=2940&auto=format&fit=crop&ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D", use_column_width=True)
    st.title("Activity Sign-up System")

    st.sidebar.title("Navigation")
    section = st.sidebar.radio("Main Menu", ["Member", "Admin"])

    if section == "Member":
        st.sidebar.subheader("Member Options")
        member_menu = st.sidebar.radio("Select Option", ["New Member Sign-up", "Browse Activities", "Activity Sign-up"])

        if member_menu == "New Member Sign-up":
            st.subheader("New Member Sign-up")
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
                st.dataframe(activities_df)
            else:
                st.warning("No activities found.")

    elif section == "Admin":
        st.sidebar.subheader("Admin Options")
        admin_menu = st.sidebar.radio("Select Admin Option", ["Generate Reports", "Data", "Manage Activities"])

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
                            st.dataframe(results)

                            csv_data = results.to_csv(index=False).encode('utf-8')

                            with io.BytesIO() as buffer:
                                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                                    results.to_excel(writer, index=False)
                                excel_data = buffer.getvalue()

                            st.download_button(
                                label="Download as CSV",
                                data=csv_data,
                                file_name='query_result.csv',
                                mime='text/csv'
                            )

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

        elif admin_menu == "Manage Activities":
            manage_activities()

if __name__ == "__main__":
    main()
