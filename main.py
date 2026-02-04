import subprocess
print("\n..:: Wi-Fi Passwords: \n")
# Get the list of all saved Wi-Fi profiles
data = subprocess.check_output(['netsh', 'wlan', 'show', 'profiles']).decode('utf-8', errors='backslashreplace').split('\n')

# Extract profile names
profiles = [line.split(":")[1].strip() for line in data if "All User Profile" in line]

# Print header for output
print(f"{'Wi-Fi Profile':<40}|  {'Password'}") # # This line prints the table header with 'Wi-Fi Profile' and 'Password' as column titles, and ensures the 'Wi-Fi Profile' column has a width of 40 characters for alignment.
print("-" * 60)

# Iterate over profiles and retrieve their passwords
for profile in profiles:
    try:
        # Get profile details
        profile_details = subprocess.check_output(['netsh', 'wlan', 'show', 'profile', profile, 'key=clear']).decode('utf-8', errors='backslashreplace').split('\n')
        
        # Extract the password (Key Content)
        password = next((line.split(":")[1].strip() for line in profile_details if "Key Content" in line), "")
        
        # Print profile name and password
        print(f"{profile:<40}|  {password}")
        
    except subprocess.CalledProcessError:
        print(f"{profile:<40}|  ENCODING ERROR")

input("\nPress Enter to exit...")
print("\n")