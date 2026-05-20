importScripts('https://www.gstatic.com/firebasejs/10.7.1/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.7.1/firebase-messaging-compat.js');

firebase.initializeApp({
    apiKey: "AIzaSyAHJJDiKPr53RPiPo7sNuHZ3TSF8CQRRIk",
    authDomain: "medicontrol-fe869.firebaseapp.com",
    projectId: "medicontrol-fe869",
    storageBucket: "medicontrol-fe869.firebasestorage.app",
    messagingSenderId: "375947697062",
    appId: "1:375947697062:web:67df29b3fd722de3030d67",
});

const messaging = firebase.messaging();

self.addEventListener('push', function(event) {
    let title = 'MediControl 💊';
    let body  = 'Tienes una toma pendiente';


    if (event.data) {
        try {
            const data = event.data.json();
            title = data.notification?.title || title;
            body  = data.notification?.body  || body;
        } catch(e) {
            title = event.data.text() || title;
        }
    }

    event.waitUntil(
        self.registration.showNotification(title, { body })
    );
});
