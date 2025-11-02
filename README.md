# AO3 Helper 📖✨

[![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**AO3 Helper** is your personal desktop archive and reading toolkit for Archive of Our Own (AO3), designed for power readers who want to go beyond browser bookmarks and gain full control over their fanfiction library.



## Core Philosophy: Your Data is Yours. Period.

This application was built with a "privacy-first" principle. We believe you should have complete ownership of your reading data.

*   **🛡️ 100% Local:** All your data (fic list, notes, ratings, credentials, and history) is stored **ONLY** on your computer. Nothing is ever sent to a third-party server. The code is open-source for you to verify.
*   **🔒 Secure Credentials:** Your AO3 password is never stored in a plain text file. It is handled by the `keyring` library, which saves it securely in the Windows Credential Manager or your operating system's native keychain.
*   **🤝 Direct Communication:** The app communicates only and directly with Archive of Our Own's servers, exactly as your web browser does.

## Features Overview (v1.9.0)

*   **📚 Smart Importer & Library Management:**
    *   Paste any AO3 URL (work, author, series, or collection) to import fics into your local library.
    *   Instantly sort, search, and filter your archive by dozens of fields, including a personalized **'Match Score'** to see how well any fic aligns with your tastes.
    *   Add personal notes, 5-star ratings, and custom organizational tags to any fic.

*   **🧠 Intelligent Recommendation & Discovery Engine:**
    *   **For You Suggestions:** Get personalized recommendations from your "To Read" list, powered by a deep analysis of your reading habits.
    *   **Discover from AO3:** Find new fics you'll love without leaving the app. The Discovery Engine builds smart queries based on your profile using unique strategies:
        *   **The Safe Bet:** Finds fics that perfectly match your top fandoms, relationships, and tags.
        *   **The Hidden Gem:** Unearths high-quality stories with low popularity.
        *   **Author-Curated:** A one-of-a-kind feature that suggests works from your favorite authors' public bookmarks.
    *   **Detailed Previews:** View a fic's complete summary, tags, and stats *before* importing it.

*   **⚡ Power User Tools:**
    *   **Reading Queue:** Organize your next reads with a dedicated, drag-and-drop reorderable queue.
    *   **Advanced Filter Builder:** Construct complex queries with `AND`, `OR`, and `NOT` logic for tags and other fields.
    *   **Saved Filters:** Save your complex searches and recall them with a single click.
    *   **Bulk Editing:** Select multiple fics at once to efficiently change their status or manage tags.
    *   **Automated Status Sync:** Connect your AO3 account to automatically verify your Kudos & Comment status across your library.

*   **🕓 Full Reading History Integration:**
    *   Import your **entire** AO3 reading history to create a complete, private archive.
    *   Enjoy **intelligent incremental syncs** that quickly fetch only your newest reads.
    *   Use the **"Inbox" view** to manage fics from your history that you haven't formally added to your library.

*   **🚀 Reader Dashboard & True Favorites Analysis:**
    *   Go beyond simple counts with a multi-tab dashboard that analyzes your reading habits.
    *   The **Analysis Engine** calculates your *true* favorite authors, tags, and relationships based on a sophisticated weighting model that considers re-reads, ratings, and engagement.
    *   Create **Pro Word Clouds** based on your unique taste profile and export them as high-quality PNG or vector SVG files.

*   **🏆 Gamification & Achievements:** Unlock achievements and level up based on the words and fics you've read.
*   **🎨 Customization:** Switch between Light and Dark themes to suit your preference.

## 🚀 What's Next? The Road to v2.0 and Beyond

With the "Power Reader" phase now complete, our strategic vision is focused on expanding the ecosystem.

*   **Phase 10: The Creator Ecosystem (v2.0):**
    *   **Writer's Dashboard:** Tools for managing Works in Progress (WIPs), chapter outlines, notes, and writing goals.
    *   **Community & Event Tools:** Features for moderators of fandom events (like exchanges or bingos) to manage participants, assignments, and deadlines.

*   **Phase 11: UX & Visual Revamp (Post-v2.0):**
    *   A full frontend refactoring to modernize the user interface based on the now-mature feature set.
    *   Advanced theming and further usability improvements based on community feedback.

## Installation & Usage

You have two options for running AO3 Helper. The recommended method for most users is the installer.

### Option 1: For End-Users (Recommended)

1.  Go to the project's **[Releases Page](https://github.com/Symphony-of-Dreams/ao3-helper/releases)**.
2.  Download the `setup.exe` file from the latest release.
3.  Run the installer.

> **⚠️ A Note on Antivirus Software**
>
> Upon first launch, your antivirus software (including Windows Defender) might flag the `.exe` as a potential threat. **This is a false positive.** It happens because the executable is not "code-signed" by a registered company, a costly process for independent developers.
>
> The application is completely safe to use. You can verify this by examining the source code in this repository.

### Option 2: For Developers (Running from Source)

If you prefer to run the application directly from the source code, you can do so by following these steps:

1.  **Install Python:** Ensure you have Python 3.11 or newer installed.
2.  **Clone the repository:**
    ```bash
    git clone https://github.com/Symphony-of-Dreams/ao3-helper.git
    cd ao3-helper
    ```
    
3.  **Create a virtual environment:**
    ```bash
    python -m venv venv
    venv\Scripts\activate  # On Windows
    ```
    
4.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
5.  **Run the application:**
    ```bash
    python main.py
    ```

## Tech Stack

*   **GUI:** PyQt6
*   **Database:** SQLite 3 with **Peewee (ORM)**
*   **AO3 Interaction:** AO3
*   **Credential Management:** keyring
*   **Data Visualization:** Matplotlib & wordcloud

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.