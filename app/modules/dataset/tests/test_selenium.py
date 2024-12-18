import os
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from core.environment.host import get_host_for_selenium_testing
from core.selenium.common import initialize_driver, close_driver


def wait_for_page_to_load(driver, timeout=4):
    WebDriverWait(driver, timeout).until(
        lambda driver: driver.execute_script("return document.readyState") == "complete"
    )


def count_datasets(driver, host):
    driver.get(f"{host}/dataset/list")
    wait_for_page_to_load(driver)

    try:
        amount_datasets = len(driver.find_elements(By.XPATH, "//table//tbody//tr"))
    except Exception:
        amount_datasets = 0
    return amount_datasets


def test_upload_dataset():
    driver = initialize_driver()

    try:
        host = get_host_for_selenium_testing()

        # Open the login page
        driver.get(f"{host}/login")
        wait_for_page_to_load(driver)

        # Find the username and password field and enter the values
        email_field = driver.find_element(By.NAME, "email")
        password_field = driver.find_element(By.NAME, "password")

        email_field.send_keys("user1@example.com")
        password_field.send_keys("1234")

        # Send the form
        password_field.send_keys(Keys.RETURN)
        wait_for_page_to_load(driver)

        # Count initial datasets
        initial_datasets = count_datasets(driver, host)

        # Open the upload dataset
        driver.get(f"{host}/dataset/upload")
        wait_for_page_to_load(driver)

        # Find basic info and UVL model and fill values
        title_field = driver.find_element(By.NAME, "title")
        title_field.send_keys("Title")
        desc_field = driver.find_element(By.NAME, "desc")
        desc_field.send_keys("Description")
        tags_field = driver.find_element(By.NAME, "tags")
        tags_field.send_keys("tag1,tag2")

        # Add two authors and fill
        add_author_button = driver.find_element(By.ID, "add_author")
        add_author_button.send_keys(Keys.RETURN)
        wait_for_page_to_load(driver)
        add_author_button.send_keys(Keys.RETURN)
        wait_for_page_to_load(driver)

        name_field0 = driver.find_element(By.NAME, "authors-0-name")
        name_field0.send_keys("Author0")
        affiliation_field0 = driver.find_element(By.NAME, "authors-0-affiliation")
        affiliation_field0.send_keys("Club0")
        orcid_field0 = driver.find_element(By.NAME, "authors-0-orcid")
        orcid_field0.send_keys("0000-0000-0000-0000")

        name_field1 = driver.find_element(By.NAME, "authors-1-name")
        name_field1.send_keys("Author1")
        affiliation_field1 = driver.find_element(By.NAME, "authors-1-affiliation")
        affiliation_field1.send_keys("Club1")

        # Obtén las rutas absolutas de los archivos
        file1_path = os.path.abspath("app/modules/dataset/uvl_examples/file1.uvl")
        file2_path = os.path.abspath("app/modules/dataset/uvl_examples/file2.uvl")

        # Subir el primer archivo
        dropzone = driver.find_element(By.CLASS_NAME, "dz-hidden-input")
        dropzone.send_keys(file1_path)
        wait_for_page_to_load(driver)

        # Subir el segundo archivo
        dropzone = driver.find_element(By.CLASS_NAME, "dz-hidden-input")
        dropzone.send_keys(file2_path)
        wait_for_page_to_load(driver)

        # Add authors in UVL models
        show_button = driver.find_element(By.ID, "0_button")
        show_button.send_keys(Keys.RETURN)
        add_author_uvl_button = driver.find_element(By.ID, "0_form_authors_button")
        add_author_uvl_button.send_keys(Keys.RETURN)
        wait_for_page_to_load(driver)

        name_field = driver.find_element(By.NAME, "feature_models-0-authors-2-name")
        name_field.send_keys("Author3")
        affiliation_field = driver.find_element(By.NAME, "feature_models-0-authors-2-affiliation")
        affiliation_field.send_keys("Club3")

        # Check I agree and send form
        check = driver.find_element(By.ID, "agreeCheckbox")
        check.send_keys(Keys.SPACE)
        wait_for_page_to_load(driver)

        upload_btn = driver.find_element(By.ID, "upload_button")
        upload_btn.send_keys(Keys.RETURN)
        wait_for_page_to_load(driver)
        time.sleep(2)  # Force wait time

        assert driver.current_url == f"{host}/dataset/list", "Test failed!"

        # Count final datasets
        final_datasets = count_datasets(driver, host)
        assert final_datasets == initial_datasets + 1, "Test failed!"

        print("Test passed!")

    finally:

        # Close the browser
        close_driver(driver)


def test_upload_dataset_zip():
    driver = initialize_driver()

    try:
        host = get_host_for_selenium_testing()

        # Open the login page
        driver.get(f"{host}/login")
        wait_for_page_to_load(driver)

        driver.find_element(By.ID, "email").send_keys("user1@example.com")
        driver.find_element(By.ID, "password").send_keys("1234")

        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, "submit"))).click()
        wait_for_page_to_load(driver)

        # Navigate to "Upload from ZIP"
        driver.get(f"{host}/dataset/upload/zip")
        wait_for_page_to_load(driver)
        wait_for_page_to_load(driver)

        # Fill out title and description
        driver.find_element(By.ID, "title").send_keys("Test Selenium IDE zip")
        driver.find_element(By.ID, "desc").send_keys("Test Selenium IDE zip")

        file_path = os.path.abspath("app/modules/dataset/uvl_examples/prueba.zip")

        if os.path.exists(file_path):
            file_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
            )
            file_input.send_keys(file_path)
        else:
            raise FileNotFoundError(f"El archivo {file_path} no se encontró.")

        check = driver.find_element(By.ID, "agreeCheckbox")
        check.send_keys(Keys.SPACE)
        wait_for_page_to_load(driver)

        upload_btn = driver.find_element(By.ID, "upload_button")
        upload_btn.send_keys(Keys.RETURN)
        wait_for_page_to_load(driver)
        time.sleep(2)

        # Assert the final URL (if required)
        assert driver.current_url == f"{host}/dataset/list", "Test failed!"

        print("Test passed!")

    finally:

        close_driver(driver)


def test_upload_dataset_github():
    driver = initialize_driver()

    try:
        host = get_host_for_selenium_testing()

        # Open the login page
        driver.get(f"{host}/login")
        wait_for_page_to_load(driver)

        driver.find_element(By.ID, "email").send_keys("user1@example.com")
        driver.find_element(By.ID, "password").send_keys("1234")

        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, "submit"))).click()
        wait_for_page_to_load(driver)

        driver.get(f"{host}/dataset/upload/github")
        wait_for_page_to_load(driver)
        wait_for_page_to_load(driver)

        # Fill out title and description
        driver.find_element(By.ID, "title").send_keys("Test Selenium IDE github")
        driver.find_element(By.ID, "desc").send_keys("Test Selenium IDE github")

        github_url = "https://github.com/jorgomde/prueba-archivos-zip-y-uvl/blob/main/prueba.zip"

        # Ingresar la URL de GitHub en el campo de texto
        github_input = driver.find_element(By.ID, "github_url")
        github_input.send_keys(github_url)

        # Pulsar el botón para agregar el enlace desde GitHub
        github_submit_button = driver.find_element(By.ID, "github-submit")
        github_submit_button.click()
        wait_for_page_to_load(driver)
        time.sleep(2)

        check = driver.find_element(By.ID, "agreeCheckbox")
        check.send_keys(Keys.SPACE)
        wait_for_page_to_load(driver)

        upload_btn = driver.find_element(By.ID, "upload_button")
        upload_btn.send_keys(Keys.RETURN)
        wait_for_page_to_load(driver)
        time.sleep(2)

        # Assert the final URL (if required)
        assert driver.current_url == f"{host}/dataset/list", "Test failed!"

        print("Test passed!")

    finally:
        close_driver(driver)


def test_download_all_dataset():
    driver = initialize_driver()

    try:

        host = get_host_for_selenium_testing()

        driver.get(f"{host}/")
        time.sleep(2)

        # Navigate to "Download All"
        driver.get(f"{host}/dataset/download/all")
        wait_for_page_to_load(driver)
        wait_for_page_to_load(driver)

        print("Test passed!")

    finally:
        close_driver(driver)


def test_download_all_dataset_logged_in():
    driver = initialize_driver()

    try:

        host = get_host_for_selenium_testing()
        # Open the login page
        driver.get(f"{host}/login")
        wait_for_page_to_load(driver)

        driver.find_element(By.ID, "email").send_keys("user1@example.com")
        driver.find_element(By.ID, "password").send_keys("1234")

        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, "submit"))).click()
        wait_for_page_to_load(driver)

        driver.get(f"{host}/")
        time.sleep(2)

        # Navigate to "Download All"
        driver.get(f"{host}/dataset/download/all")
        time.sleep(2)

        wait_for_page_to_load(driver)
        wait_for_page_to_load(driver)

        print("Test passed!")

    finally:
        close_driver(driver)


def test_community():
    driver = initialize_driver()

    try:
        host = get_host_for_selenium_testing()
        driver.get(host + "/login")
        wait_for_page_to_load(driver)
        driver.find_element(By.LINK_TEXT, "Login").click()
        driver.find_element(By.ID, "email").click()
        driver.find_element(By.ID, "email").send_keys("user1@example.com")
        driver.find_element(By.ID, "password").click()
        driver.find_element(By.ID, "password").send_keys("1234")
        driver.find_element(By.ID, "password").send_keys(Keys.ENTER)
        wait_for_page_to_load(driver)
        driver.get(host + "/communities")
        driver.find_element(By.LINK_TEXT, "Create Community").click()
        wait_for_page_to_load(driver)
        driver.find_element(By.ID, "name").click()
        driver.find_element(By.ID, "name").send_keys("Prueba")
        driver.find_element(By.CSS_SELECTOR, ".btn-primary").click()
        wait_for_page_to_load(driver)
        driver.find_element(By.LINK_TEXT, "Prueba").click()
        driver.find_element(By.LINK_TEXT, "Edit Community").click()
        wait_for_page_to_load(driver)
        driver.find_element(By.ID, "name").click()
        driver.find_element(By.ID, "name").send_keys("Prueba de Selenium")
        wait_for_page_to_load(driver)
        driver.find_element(By.CSS_SELECTOR, ".btn-primary").click()
        driver.find_element(By.CSS_SELECTOR, ".btn-danger").click()
        driver.switch_to.alert.accept()

        assert driver.current_url == f"{host}/communities", "Test failed!"
        print("Test passed!")

    finally:
        close_driver(driver)


# Call the test functions
test_upload_dataset()

test_download_all_dataset()

test_download_all_dataset_logged_in()

test_upload_dataset_github()

test_upload_dataset_zip()

test_community()
