FROM amazon/aws-lambda-python:3.12

# Install chrome dependencies
RUN dnf install -y curl-minimal\
    atk cups-libs gtk3 libXcomposite alsa-lib \
    libXcursor libXdamage libXext libXi libXrandr \
    libXScrnSaver libXtst pango at-spi2-atk libXt \
    xorg-x11-server-Xvfb xorg-x11-xauth dbus-glib \
    dbus-glib-devel nss mesa-libgbm jq unzip \
    && dnf clean all \
    && rm -rf /var/cache/dnf

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY twscrape_lambda.py ./

COPY ./chrome-installer.sh .
RUN chmod +x chrome-installer.sh && ./chrome-installer.sh && rm chrome-installer.sh

CMD ["twscrape_lambda.lambda_handler"]
