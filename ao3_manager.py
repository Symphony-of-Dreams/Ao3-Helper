import random
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import AO3
from AO3 import requester
from AO3.utils import workid_from_url

import constants as const
import security_manager
from config_manager import config_manager
from logger_setup import logger

DEFAULT_REQUEST_DELAY = 2
SYNC_REQUEST_DELAY = 1
RATE_LIMIT_DELAY = 60


class AO3Client:
    session: Optional[AO3.Session]
    guest_requester: requester.Requester

    def __init__(self) -> None:
        self.session = self._create_session()
        self.guest_requester = requester.Requester()

    def _create_session(self) -> Optional[AO3.Session]:
        """
        Internal method to create and authenticate the AO3 session.
        This is called only once when the client is initialized.
        Includes a retry mechanism for rate-limiting errors.
        """
        username = config_manager.get(const.CONFIG_SECTION_CREDS, const.CONFIG_KEY_USERNAME, fallback="")
        password = security_manager.get_password(username)

        if not username or not password or username == const.CONFIG_DEFAULT_USER:
            logger.info("Credentials not configured. Proceeding as a guest.")
            return None

        logger.info(f"Found credentials for user '{username}'. Attempting login...")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                session = AO3.Session(username, password)
                logger.info("AO3 login successful!")
                return session
            except AO3.utils.HTTPError as e:
                if "rate-limited" in str(e).lower():
                    logger.warning(
                        f"Login attempt {attempt + 1}/{max_retries} was rate-limited. Retrying in {const.RATE_LIMIT_DELAY} seconds..."  # noqa: E501
                    )
                    if attempt + 1 < max_retries:
                        time.sleep(const.RATE_LIMIT_DELAY)
                    continue
                else:

                    logger.error(f"AO3 login failed due to a non-recoverable HTTP error: {e}")
                    return None
            except Exception as e:

                logger.error(f"AO3 login failed! Check credentials in config.ini. Details: {e}")
                return None

        logger.error(
            f"AO3 login failed after {max_retries} attempts due to persistent rate-limiting. Proceeding as guest."
        )
        return None

    def reload_session(self) -> bool:
        """
        Attempts to create a new AO3 session using the current credentials
        from the configuration. This allows for dynamic login/logout without
        restarting the application.

        Returns:
            True if the session was created successfully, False otherwise.
        """
        logger.info("Reloading AO3 session on demand...")
        self.session = self._create_session()
        return self.session is not None

    def fetch_fic_data(self, url: str, authenticated_fallback: bool = False) -> Optional[Dict[str, Any]]:
        logger.debug(f"Attempting to fetch data for URL: {url}")

        try:

            work_id = int(url.split("/")[-1])
            guest_work = AO3.Work(work_id, load=False)
            guest_work._requester = self.guest_requester
            guest_work.reload()
            work = guest_work

        except (AttributeError, AO3.utils.AuthError):

            logger.warning(f"Guest fetch failed for {url}. It may be private or deleted.")

            if authenticated_fallback and self.session:
                logger.info(f"Executing authenticated fallback for {url}. This will count as a visit.")
                try:

                    work = AO3.Work(work_id, session=self.session)

                except Exception as auth_e:
                    logger.error(f"Authenticated fallback also failed for {url}. Details: {auth_e}")
                    return None
            else:

                return None
        except AO3.utils.HTTPError as e:

            logger.warning(f"Network error fetching {url}. Details: {e}")

            return None
        except Exception:
            logger.exception(f"An unexpected error occurred while fetching data for URL: {url}")
            return None

        if work is None or not hasattr(work, "title") or work.title is None:
            logger.error(f"Failed to retrieve a valid Work object for ID: {work.workid if work else url}")
            return None

        nchapters = work.nchapters
        expected_chapters = work.expected_chapters
        chapters_str = f"{nchapters}/{expected_chapters or '?'}"
        is_complete = expected_chapters is not None and nchapters == expected_chapters

        series_name = ""
        series_url = ""
        series_part = None
        if work.series:
            main_series = work.series[0]
            series_name = main_series.name
            series_url = main_series.url

        date_published = work.date_published.strftime("%Y-%m-%d") if work.date_published else ""
        date_updated = work.date_updated.strftime("%Y-%m-%d") if work.date_updated else ""

        language = work.language or ""
        hits = work.hits or 0
        kudos = work.kudos or 0
        bookmarks = work.bookmarks or 0
        comments = work.comments or 0
        source = "manual"

        fic_details = {
            "url": work.url,
            "title": work.title,
            "author": ", ".join(user.username for user in work.authors),
            "summary": work.summary,
            "rating": (", ".join(work.rating) if isinstance(work.rating, list) else work.rating),
            "fandoms": ", ".join(work.fandoms),
            "tags": ", ".join(work.tags),
            "word_count": work.words,
            "category": ", ".join(work.categories),
            "relationships": ", ".join(work.relationships),
            "characters": ", ".join(work.characters),
            "is_complete": is_complete,
            "series_name": series_name,
            "series_url": series_url,
            "series_part": series_part,
            "chapters": chapters_str,
            "date_published": date_published,
            "date_updated": date_updated,
            "source": source,
            "language": language,
            "hits": hits,
            "kudos": kudos,
            "bookmarks": bookmarks,
            "comments": comments,
        }

        logger.info(f"Successfully fetched data for '{work.title}' (ID: {work_id}).")
        return fic_details

    def get_work_ids_from_user(self, url_or_username: str) -> List[int] | Dict[str, str]:
        logger.info(f"Fetching all work IDs for user: {url_or_username}")
        try:
            match = re.search(r"users/([^/]+)", url_or_username)
            username = match.group(1) if match else url_or_username
            user = AO3.User(username, session=self.session)
            page, all_work_ids = 1, []
            while True:
                logger.debug(f"Fetching works from page {page} for user {username}")
                works_page_url = f"https://archiveofourown.org/users/{user.username}/works?page={page}"
                page_soup = user.request(works_page_url)
                works_list = page_soup.find("ol", {"class": "work index group"})
                if not works_list:
                    logger.debug("No more works list found. Ending search.")
                    break
                found_works_on_page = False
                for header in works_list.find_all("h4", {"class": "heading"}):
                    link = header.find("a")
                    if link and "href" in link.attrs:
                        work_id = workid_from_url(link["href"])
                        if work_id not in all_work_ids:
                            all_work_ids.append(work_id)
                            found_works_on_page = True
                if not found_works_on_page:
                    logger.debug("No new works found on this page. Ending search.")
                    break
                time.sleep(const.DEFAULT_REQUEST_DELAY)
                page += 1
            logger.info(f"Found {len(all_work_ids)} works in total for user {username}.")
            return all_work_ids
        except Exception as e:
            if "Couldn't find user" in str(e):
                logger.error(f"User '{username}' could not be found on AO3.")
                return {"error": f"User '{username}' could not be found."}
            logger.exception(f"An unexpected error occurred while fetching works for {url_or_username}")
            return {"error": "An unexpected error occurred while fetching author's works."}

    def check_kudos(self, work_id: int, username: str) -> bool:
        if not username:
            return False
        logger.debug(f"Checking kudos for user '{username}' on work {work_id}...")
        try:
            temp_work = AO3.Work(work_id, session=self.session)
            page = 1
            while True:
                kudos_url = f"https://archiveofourown.org/works/{work_id}/kudos?page={page}"
                logger.debug(f"Scraping kudos page: {kudos_url}")
                soup = temp_work.request(kudos_url)
                kudos_list = soup.find("div", {"id": "kudos"})
                if not kudos_list:
                    break
                if kudos_list.find(string=re.compile(username, re.IGNORECASE)):
                    logger.info(f"Kudos found for user '{username}' on work {work_id}.")
                    return True
                next_page = soup.find("li", {"class": "next"})
                if not next_page or next_page.find("span", {"class": "disabled"}):
                    break
                page += 1

                time.sleep(const.SYNC_REQUEST_DELAY)

        except AO3.utils.HTTPError as e:
            logger.warning(
                f"Rate-limit hit while checking kudos for work {work_id}. Pausing for {const.RATE_LIMIT_DELAY} seconds. Details: {e}"  # noqa: E501
            )
            time.sleep(const.RATE_LIMIT_DELAY)
            return False

        except Exception as e:
            logger.error(f"An error occurred while checking kudos: {e}")

        logger.info(f"Kudos not found for user '{username}' on work {work_id}.")
        return False

    def check_comment(self, work_id: int, username: str) -> bool:
        if not username:
            return False
        logger.debug(f"Checking comments for user '{username}' on work {work_id}...")
        try:
            work = AO3.Work(work_id, load=False)
            work._requester = self.guest_requester

            if not work.chapters:
                work.reload()

            for i in range(work.nchapters):
                chapter_number = i + 1
                if work.nchapters > 1:
                    logger.debug(f"Checking comments for chapter {chapter_number}/{work.nchapters}...")

                work.chapter = chapter_number
                chapter_comments = work.get_comments(9999)

                for comment in chapter_comments:
                    if (
                        hasattr(comment, "author")
                        and hasattr(comment.author, "username")
                        and comment.author.username.lower() == username.lower()
                    ):
                        logger.info(f"Comment found for user '{username}' on work {work_id}.")
                        return True

                    time.sleep(0.5)

                    for reply in comment.get_thread():
                        if (
                            hasattr(reply, "author")
                            and hasattr(reply.author, "username")
                            and reply.author.username.lower() == username.lower()
                        ):
                            logger.info(f"Comment (in thread) found for user '{username}' on work {work_id}.")
                            return True
                if work.nchapters > 1:
                    time.sleep(const.SYNC_REQUEST_DELAY)

        except AO3.utils.HTTPError as e:
            logger.warning(
                f"Rate-limit hit while checking comments for work {work_id}. Pausing for {const.RATE_LIMIT_DELAY} seconds. Details: {e}"  # noqa: E501
            )
            time.sleep(const.RATE_LIMIT_DELAY)

            return False

        except Exception:
            logger.exception(f"An unexpected error occurred while checking comments for work {work_id}")

        logger.info(f"Comment not found for user '{username}' on work {work_id}.")
        return False

    def get_bookmarks_from_user(self) -> List[int] | Dict[str, str]:
        """
        Recupera tutti i work ID dai bookmark dell'utente loggato.
        Richiede una sessione autenticata.
        """
        if not self.session:
            logger.error("Bookmark fetch failed: user is not logged in.")
            return {"error": "You must be logged in to fetch bookmarks."}

        username = self.session.username
        logger.info(f"Fetching all bookmarks for user: {username}")

        try:
            page = 1
            all_work_ids = []

            while True:
                logger.debug(f"Fetching bookmarks from page {page} for user {username}")
                bookmarks_url = f"https://archiveofourown.org/users/{username}/bookmarks?page={page}"
                page_soup = self.session.request(bookmarks_url)

                bookmarks_list = page_soup.find("ol", class_="bookmark index group")

                if not bookmarks_list:
                    logger.debug("No more bookmark lists found. Ending search.")
                    break

                found_works_on_page = False
                for li_element in bookmarks_list.find_all("li", role="article"):
                    header = li_element.find("h4", class_="heading")
                    if not header:
                        continue

                    link = header.find("a")
                    if link and "href" in link.attrs and "/works/" in link["href"]:
                        work_id = workid_from_url(link["href"])
                        if work_id not in all_work_ids:
                            all_work_ids.append(work_id)
                            found_works_on_page = True

                if not found_works_on_page:
                    logger.debug("No new works found on this page. Ending search.")
                    break

                next_page_link = page_soup.select_one("li.next a")
                if not next_page_link:
                    logger.debug("No 'next page' link found. Ending bookmarks search.")
                    break

                time.sleep(const.DEFAULT_REQUEST_DELAY)
                page += 1

            logger.info(f"Found {len(all_work_ids)} bookmarks in total for user {username}.")
            return all_work_ids

        except Exception:
            logger.exception(f"An unexpected error occurred while fetching bookmarks for {username}")
            return {"error": "An unexpected error occurred while fetching bookmarks."}

    def get_random_bookmarks_from_author(self, username: str, num_to_sample: int = 5) -> List[int]:
        """
        Recupera un campione casuale di work ID dai bookmark pubblici di un utente,
        scegliendo una pagina a caso per essere più efficiente.
        """
        logger.info(f"Fetching random bookmarks sample for user: {username}")
        try:

            base_url = f"https://archiveofourown.org/users/{username}/bookmarks"

            response = self.guest_requester.request("GET", base_url)

            page_soup = AO3.utils.BeautifulSoup(response.text, "html.parser")

            max_pages = 1
            pagination = page_soup.find("ol", {"class": "pagination actions"})
            if pagination:
                page_links = pagination.find_all("a")
                if len(page_links) > 1:
                    try:
                        max_pages = int(page_links[-2].text)
                    except (ValueError, IndexError):
                        max_pages = 1

            random_page = random.randint(1, max_pages)
            logger.debug(f"Randomly selected page {random_page}/{max_pages} for {username}")

            page_url = f"{base_url}?page={random_page}"

            response = self.guest_requester.request("GET", page_url)

            page_soup = AO3.utils.BeautifulSoup(response.text, "html.parser")

            page_work_ids = []
            bookmarks_list = page_soup.find("ol", class_="bookmark index group")
            if bookmarks_list:
                for li_element in bookmarks_list.find_all("li", role="article"):
                    header = li_element.find("h4", class_="heading")
                    if not header:
                        continue
                    link = header.find("a")
                    if link and "href" in link.attrs and "/works/" in link["href"]:
                        page_work_ids.append(workid_from_url(link["href"]))

            final_sample_size = min(num_to_sample, len(page_work_ids))
            return random.sample(page_work_ids, final_sample_size)

        except Exception:
            logger.exception(f"An unexpected error occurred while fetching random bookmarks for {username}")
            return []

    def get_work_ids_from_collection(self, collection_name: str) -> List[int] | Dict[str, str]:
        logger.info(f"Fetching all work IDs for collection: {collection_name}")
        try:
            page, all_work_ids = 1, []

            while True:
                logger.debug(f"Fetching works from page {page} for collection {collection_name}")

                collection_url = f"https://archiveofourown.org/collections/{collection_name}/works?page={page}"

                page_soup = (
                    self.session.request(collection_url) if self.session else AO3.utils.Request().get(collection_url)
                )

                works_list = page_soup.find("ol", {"class": "work index group"})
                if not works_list:
                    logger.debug("No more works list found. Ending search.")
                    break

                found_works_on_page = False
                for header in works_list.find_all("h4", {"class": "heading"}):
                    link = header.find("a")
                    if link and "href" in link.attrs:
                        work_id = workid_from_url(link["href"])
                        if work_id not in all_work_ids:
                            all_work_ids.append(work_id)
                            found_works_on_page = True

                if not found_works_on_page:
                    logger.debug("No new works found on this page. Ending search.")
                    break

                time.sleep(const.DEFAULT_REQUEST_DELAY)
                page += 1

            logger.info(f"Found {len(all_work_ids)} works in total for collection {collection_name}.")
            return all_work_ids

        except Exception as e:
            if "That page doesn't exist" in str(e) or "404 Not Found" in str(e):
                logger.error(f"Collection '{collection_name}' could not be found on AO3.")
                return {"error": f"Collection '{collection_name}' could not be found."}

            logger.exception(f"An unexpected error occurred while fetching works for collection {collection_name}")
            return {"error": "An unexpected error occurred while fetching collection's works."}

    def get_work_ids_from_series(self, series_id: str) -> List[int] | Dict[str, str]:
        """
        Recupera tutti i work ID da una serie tramite parsing diretto dell'HTML.
        Questo approccio è più robusto e non dipende da oggetti API inaffidabili.
        """
        logger.info(f"Fetching all work IDs for series ID: {series_id} via direct HTML parsing.")
        try:
            page, all_work_ids = 1, []
            while True:
                logger.debug(f"Fetching works from page {page} for series {series_id}")
                series_url = f"https://archiveofourown.org/series/{series_id}?page={page}"

                page_soup = self.session.request(series_url) if self.session else AO3.utils.Request().get(series_url)

                work_links = page_soup.select("li.work h4.heading a")

                if not work_links:
                    logger.debug("No work links found on this page with the specific selector. Ending search.")
                    break

                found_works_on_page = False
                for link in work_links:
                    if "href" in link.attrs and "/works/" in link["href"]:
                        work_id = workid_from_url(link["href"])
                        if work_id not in all_work_ids:
                            all_work_ids.append(work_id)
                            found_works_on_page = True

                if not found_works_on_page:
                    logger.debug("No new works found on this page, likely the end of the series. Ending search.")
                    break

                next_page_link = page_soup.select_one("li.next a")
                if not next_page_link:
                    logger.debug("No 'next page' link found. Ending search.")
                    break

                time.sleep(const.DEFAULT_REQUEST_DELAY)
                page += 1

            logger.info(f"Found {len(all_work_ids)} works in total for series {series_id}.")
            return all_work_ids

        except Exception as e:
            if "That page doesn't exist" in str(e) or "404 Not Found" in str(e):
                logger.error(f"Series ID '{series_id}' could not be found on AO3.")
                return {"error": f"Series ID '{series_id}' could not be found."}

            logger.exception(f"An unexpected error occurred while fetching works for series {series_id}")
            return {"error": "An unexpected error occurred while fetching the series."}

    def get_history_from_user(self) -> List[Dict[str, Any]] | Dict[str, str]:
        """
        Recupera l'intera cronologia di lettura ("History") per l'utente loggato.
        Richiede una sessione autenticata.
        """
        if not self.session:
            logger.error("History fetch failed: user is not logged in.")
            return {"error": "You must be logged in to fetch your reading history."}

        username = self.session.username
        logger.info(f"Fetching full reading history for user: {username}")

        try:
            page = 1
            all_history_items = []

            while True:
                logger.debug(f"Fetching history from page {page} for user {username}")
                history_url = f"https://archiveofourown.org/users/{username}/readings?page={page}"
                page_soup = self.session.request(history_url)

                history_list = page_soup.find("ol", class_="reading work index group")

                if not history_list:
                    logger.debug(
                        f"Primary container ('ol.reading.work.index.group') not found on page {page}. Ending search."
                    )
                    break

                work_items = history_list.find_all("li", role="article")

                if not work_items:
                    logger.debug(f"Container found, but no work items found on page {page}. Ending search.")
                    break

                for item in work_items:
                    header = item.find("h4", class_="heading")
                    link = header.find("a") if header else None
                    if not (link and "href" in link.attrs and "/works/" in link["href"]):
                        continue

                    work_id = workid_from_url(link["href"])

                    visit_count = 1
                    last_visit_date = ""

                    viewed_heading = item.find("h4", class_="viewed heading")
                    if viewed_heading:
                        full_text = viewed_heading.get_text(strip=True)

                        date_match = re.search(r"Last visited:.*?(\d{1,2}\s\w{3}\s\d{4})", full_text)
                        if date_match:
                            try:
                                date_str = date_match.group(1).strip()
                                date_obj = datetime.strptime(date_str, "%d %b %Y")
                                last_visit_date = date_obj.strftime("%Y-%m-%d")
                            except (ValueError, AttributeError):
                                logger.warning(
                                    f"Could not parse date for work {work_id} from string: '{date_match.group(1)}'"
                                )
                                pass

                        times_match = re.search(r"Visited (\d+) time", full_text)
                        if times_match:
                            visit_count = int(times_match.group(1))
                        elif "Last visited" in full_text:
                            visit_count = 1

                    all_history_items.append(
                        {
                            "work_id": work_id,
                            "last_visit_date": last_visit_date,
                            "visit_count": visit_count,
                        }
                    )

                next_page_link = page_soup.select_one("li.next a")
                if not next_page_link:
                    logger.debug("No 'next page' link found. Ending history search.")
                    break

                time.sleep(const.DEFAULT_REQUEST_DELAY)
                page += 1

            logger.info(f"Found {len(all_history_items)} history entries in total for user {username}.")
            return all_history_items

        except Exception:
            logger.exception(f"An unexpected error occurred while fetching history for {username}")
            return {"error": "An unexpected error occurred while fetching your history."}


ao3_client = AO3Client()


def parse_ao3_url(url: str) -> tuple[str, str | None]:
    """
    Analyzes an AO3 URL and determines its type and identifier.

    Returns:
        A tuple containing (url_type, identifier).
        url_type can be 'work', 'author', 'collection', 'series', or 'unknown'.
        identifier is the extracted ID or name, or None.
    """
    work_match = re.search(r"/works/(\d+)", url)
    if work_match:
        return ("work", work_match.group(1))

    author_works_match = re.search(r"/users/([^/]+)/works", url)
    if author_works_match:
        return ("author", author_works_match.group(1))

    author_profile_match = re.search(r"/users/([^/]+)", url)
    if author_profile_match:
        return ("author", author_profile_match.group(1))

    collection_match = re.search(r"/collections/([^/]+)", url)
    if collection_match:
        return ("collection", collection_match.group(1).split("/")[0])

    series_match = re.search(r"/series/(\d+)", url)
    if series_match:
        return ("series", series_match.group(1))

    return ("unknown", None)
