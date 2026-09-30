document.addEventListener("DOMContentLoaded", function () {
    console.log("Lead Management System JavaScript loaded successfully.");
});
function prepareActivity(activityType) {

    const activitySelect = document.querySelector(
        'select[name="activity_type"]'
    );

    const descriptionField = document.querySelector(
        'textarea[name="description"]'
    );

    if (!activitySelect) {
        return;
    }

    activitySelect.value = activityType;

    if (descriptionField) {
        descriptionField.focus();
    }

    const activitySection = document.querySelector(
        '.timeline'
    );

    if (activitySection) {
        activitySection.scrollIntoView({
            behavior: 'smooth',
            block: 'center'
        });
    }
}