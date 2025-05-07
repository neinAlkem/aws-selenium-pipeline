
FROM amazon/aws-lambda-python:3.12
# Install chrome dependencies
RUN dnf install -y atk cups-libs gtk3 libXcomposite alsa-lib \
    libXcursor libXdamage libXext libXi libXrandr libXScrnSaver \
    libXtst pango at-spi2-atk libXt xorg-x11-server-Xvfb \
    xorg-x11-xauth dbus-glib dbus-glib-devel nss mesa-libgbm jq unzip \
    && dnf clean all \
    && rm -rf /var/cache/dnf

# Copy and run the chrome installer script
COPY ./chrome-installer.sh ./chrome-installer.sh
RUN chmod +x ./chrome-installer.sh
RUN ./chrome-installer.sh
RUN rm ./chrome-installer.sh

# Install selenium
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy the main application code
COPY lambda_aws.py ./
# Command to run the Lambda function
CMD [ "lambda_aws.lambda_process" ]
