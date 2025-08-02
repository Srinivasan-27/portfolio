'use strict';

//
// Element toggle function
//
const toggleElement = (elem) => elem.classList.toggle("active");


//
// Sidebar toggle functionality for mobile
//
const sidebar = document.querySelector("[data-sidebar]");
const sidebarBtn = document.querySelector("[data-sidebar-btn]");
if (sidebarBtn) {
  sidebarBtn.addEventListener("click", () => toggleElement(sidebar));
}


//
// Image modal functionality
//
const modal = document.getElementById("myModal");
const avatarImage = document.getElementById("avatarImage");
const modalImg = document.getElementById("img01");
const closeModal = document.getElementsByClassName("close")[0];

if (avatarImage) {
  avatarImage.onclick = function() {
    if(modal) modal.style.display = "block";
    if(modalImg) modalImg.src = this.src;
  }
}

if (closeModal) {
  closeModal.onclick = function() {
    if(modal) modal.style.display = "none";
  }
}

window.onclick = function(event) {
    if (event.target == modal) {
        modal.style.display = "none";
    }
}


//
// Right-click protection for all images
//
document.addEventListener('contextmenu', function(e) {
  if (e.target.nodeName === 'IMG') {
    e.preventDefault();
  }
}, false);


//
// Dynamic Avatar Rotation
//
const avatarImages = [
  '/static/images/profile.jpeg',
  '/static/images/my-avatar.png' 
];
let currentAvatarIndex = 0;

if (avatarImage) {
  setInterval(() => {
    // Increment index or loop back to 0
    currentAvatarIndex = (currentAvatarIndex + 1) % avatarImages.length;
    
    // Fade out the image
    avatarImage.style.opacity = '0';
    
    // Change the source after the fade-out transition has started
    setTimeout(() => {
      avatarImage.src = avatarImages[currentAvatarIndex];
      // Fade the new image back in
      avatarImage.style.opacity = '1';
    }, 500); // This delay should match the opacity transition duration in CSS
  }, 5000); // Change image every 5 seconds
}


//
// Custom select and portfolio filter functionality
//
const select = document.querySelector("[data-select]");
const selectItems = document.querySelectorAll("[data-select-item]");
const selectValue = document.querySelector("[data-select-value]");
const filterBtns = document.querySelectorAll("[data-filter-btn]");
const filterItems = document.querySelectorAll("[data-filter-item]");

if (select) {
    select.addEventListener("click", () => toggleElement(select));

    selectItems.forEach(item => {
      item.addEventListener("click", () => {
        const selectedValue = item.innerText.toLowerCase();
        selectValue.innerText = item.innerText;
        toggleElement(select);
        filterItems.forEach(filterItem => {
          filterItem.classList.toggle(
            "active",
            selectedValue === "all" || selectedValue === filterItem.dataset.category
          );
        });
      });
    });

    let lastClickedBtn = filterBtns[0];
    filterBtns.forEach(btn => {
      btn.addEventListener("click", () => {
        const selectedValue = btn.innerText.toLowerCase();
        selectValue.innerText = btn.innerText;
        filterItems.forEach(filterItem => {
          filterItem.classList.toggle(
            "active",
            selectedValue === "all" || selectedValue === filterItem.dataset.category
          );
        });
        lastClickedBtn.classList.remove("active");
        btn.classList.add("active");
        lastClickedBtn = btn;
      });
    });
}


//
// Contact form validation and submission
//
const form = document.querySelector("[data-form]");
const formInputs = document.querySelectorAll("[data-form-input]");
const formBtn = document.querySelector("[data-form-btn]");

if (form) {
    const notification = document.createElement("div");
    notification.classList.add("notification");
    document.body.appendChild(notification);

    // Validate form on input
    formInputs.forEach(input => {
      input.addEventListener("input", () => {
        formBtn.disabled = !form.checkValidity();
      });
    });

    // Form submission
    form.addEventListener("submit", async (e) => {
      e.preventDefault();

      // Disable button during submission
      formBtn.disabled = true;
      formBtn.innerHTML = `<ion-icon name="hourglass-outline"></ion-icon><span>Sending...</span>`;

      try {
        const formData = new FormData(form);
        const response = await fetch('/api/contact', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(Object.fromEntries(formData))
        });

        if (response.ok) {
          showNotification('Message sent successfully!');
          form.reset();
        } else {
          throw new Error('Failed to send message');
        }
      } catch (error) {
        showNotification('Error sending message. Please try again.', true);
      } finally {
        formBtn.disabled = false;
        formBtn.innerHTML = `<ion-icon name="paper-plane"></ion-icon><span>Send Message</span>`;
      }
    });

    function showNotification(message, isError = false) {
      notification.textContent = message;
      notification.style.backgroundColor = isError ? 'var(--bittersweet-shimmer)' : 'var(--onyx)';
      notification.classList.add('active');

      setTimeout(() => {
        notification.classList.remove('active');
      }, 3000);
    }

    // Initialize form button state
    formBtn.disabled = !form.checkValidity();
}


//
// Page navigation functionality
//
const navigationLinks = document.querySelectorAll("[data-nav-link]");
const pages = document.querySelectorAll("[data-page]");

navigationLinks.forEach(link => {
  link.addEventListener("click", () => {
    const targetPage = link.innerHTML.toLowerCase();
    pages.forEach(page => {
      page.classList.toggle("active", page.dataset.page === targetPage);
    });
    navigationLinks.forEach(navLink => {
      navLink.classList.toggle("active", navLink === link);
    });
    window.scrollTo(0, 0);
  });
});