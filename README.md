# RescueNet AI 🚨

RescueNet AI is an AI-powered emergency response platform that I’m building to make disaster and rescue operations easier to manage and coordinate.

The main idea is to provide a common platform where teams like **NDRF, SDRF, police, fire services, and volunteers** can share information, report incidents, and keep track of ongoing rescue operations.

### ✨ Key Features

* 🚨 **Emergency Reporting** — Report and track incidents from the field.
* 👥 **Multi-Agency Coordination** — Helps different response teams work together on the same platform.
* 📴 **Offline-First Support** — Designed to work even when internet connectivity is weak or unavailable.
* 📍 **Operational Tracking** — Keep track of search-and-rescue activities across different areas.
* 📡 **Real-Time Updates** — Uses MQTT for sending operational notifications and updates.
* 🔄 **Data Synchronization** — Offline data can be synchronized when connectivity becomes available.
* 🗂️ **Event-Based Data** — Important operational actions are stored as events instead of simply overwriting previous information.
* 📱 **Field Application** — Android application designed for teams working directly at disaster sites.
* 🖥️ **Command Dashboard** — Web dashboard for commanders to monitor and coordinate operations.
* 📲 **SMS Fallback** — SMS is being explored as an additional communication option for situations with limited connectivity.

### 🛠️ Tech Stack

* **Backend:** Python, FastAPI
* **Mobile:** Kotlin, Android
* **Dashboard:** React + TypeScript
* **Database:** PostgreSQL
* **Communication:** MQTT / Mosquitto
* **Deployment:** Docker Compose

### 🎯 Goal

The goal of RescueNet AI is to create a reliable system that helps emergency teams **share information, stay coordinated, and manage rescue operations more effectively**, especially in situations where normal communication infrastructure may not be available.

> 🚧 **Project Status:** Currently under development. The requirements, architecture, feasibility analysis, and implementation plan have been completed, and application development is in progress.
