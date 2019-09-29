FROM microsoft/dotnet:2.2-sdk
ARG BUILD_CONFIGURATION=Debug
ENV ASPNETCORE_ENVIRONMENT=Development
ENV DOTNET_USE_POLLING_FILE_WATCHER=true
EXPOSE 80

WORKDIR /src
COPY . shatAuthsample
RUN dotnet restore shatAuthsample/SignalRAuthenticationSample.csproj
RUN apt-get update -yq && apt-get upgrade -yq && apt-get install -yq curl git nano
RUN curl -sL https://deb.nodesource.com/setup_8.x | bash - && apt-get install -yq nodejs build-essential
RUN npm install -g npm

COPY . .
WORKDIR  /src/shatAuthsample
RUN npm install
RUN npm build
RUN dotnet build --no-restore -c $BUILD_CONFIGURATION

ENTRYPOINT ["dotnet", "run", "--no-launch-profile", "-c", "Debug", "--"]