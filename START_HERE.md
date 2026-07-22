# Start here: GitHub first, then Streamlit

You do **not** need Python, GitHub Desktop, Codespaces, or a command line.

## Step 1: Put the project on GitHub

1. Extract the ZIP.
2. Open the extracted folder. You should immediately see `app.py`, `requirements.txt`, `.github`, `.streamlit`, and the other project folders.
3. Sign in to GitHub and create a new repository named `mushroom-watch`.
4. Leave **Add a README**, **.gitignore**, and **license** unchecked because this package already contains them.
5. On the empty repository page, choose **uploading an existing file**.
6. In the extracted folder, press **Ctrl+A** and drag everything onto GitHub's upload page.
7. Wait for the files to finish loading, then click **Commit changes**.

At the repository root, you should see `app.py` and `requirements.txt`. Do not upload the ZIP itself as the only repository file.

## Step 2: Deploy the GitHub repository to Streamlit

1. Sign in to Streamlit Community Cloud with the same GitHub account.
2. Connect Streamlit to GitHub when prompted.
3. Click **Create app**.
4. Choose **Yup, I have an app**.
5. Select your `mushroom-watch` repository.
6. Use branch `main`.
7. Enter `app.py` for the main file path.
8. In **Advanced settings**, choose Python 3.12.
9. Optional: in **Secrets**, enter:

   ```toml
   MUSHROOM_WATCH_REPOSITORY = "YOUR-GITHUB-USERNAME/mushroom-watch"
   ```

10. Click **Deploy**.

Streamlit will provide a permanent `streamlit.app` address. Future commits to GitHub automatically update the deployed app.

## Step 3: Optional automatic phone alerts

The dashboard works without ntfy. Set this up only after the app is deployed.

1. In GitHub, open **Settings → Secrets and variables → Actions**.
2. Add a repository secret named `NTFY_TOPIC`.
3. Put your private ntfy topic in the value field.
4. Open **Actions → Mushroom alerts → Run workflow**.
5. Keep **Dry run** enabled for the first test.

Scheduled alerts run through GitHub Actions. The public dashboard runs through Streamlit Community Cloud.

## What controls what?

- **GitHub** stores the code, configuration, field-observation Issue Form, tests, and scheduled alert workflow.
- **Streamlit Community Cloud** reads `app.py` and `requirements.txt` from GitHub and hosts the dashboard.
- **ntfy** receives optional notifications sent by GitHub Actions.
