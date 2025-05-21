FROM amazon/aws-lambda-python:3.12

# Install chrome dependencies
RUN dnf install -y \
    atk cups-libs gtk3 libXcomposite alsa-lib \
    libXcursor libXdamage libXext libXi libXrandr \
    libXScrnSaver libXtst pango at-spi2-atk libXt \
    xorg-x11-server-Xvfb xorg-x11-xauth dbus-glib \
    dbus-glib-devel nss mesa-libgbm jq unzip \
    && dnf clean all \
    && rm -rf /var/cache/dnf

# Install Node.js 20.x
RUN curl -fsSL https://rpm.nodesource.com/setup_20.x | bash - \
    && dnf install -y nodejs \
    && rm -rf /var/cache/yum

# Configure npm in /tmp with correct permissions
RUN mkdir -p /tmp/.npm/{_logs,bin,lib} \
    && chmod -R 777 /tmp/.npm \
    && npm config set cache /tmp/.npm \
    && npm config set prefix /tmp/.npm \
    && npm config set update-notifier false

# Install tweet-harvest directly (avoid npx issues)
RUN npm install -g tweet-harvest@2.6.1 --prefix /tmp/.npm \
    && chmod -R 777 /tmp/.npm

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY aws_function.py ./
COPY chrome-installer.sh ./

# Set up Chrome (if needed for GoFood scraping)
RUN chmod +x chrome-installer.sh \
    && ./chrome-installer.sh

# Final environment setup
ENV PATH="/tmp/.npm/bin:${PATH}" \
    NPM_CONFIG_PREFIX="/tmp/.npm" \
    NPM_CONFIG_CACHE="/tmp/.npm"

CMD ["aws_function.lambda_process"]